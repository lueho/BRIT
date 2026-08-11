# Kept free of BuildKit-only syntax (cache/bind mounts): Heroku builds this
# file with a pre-BuildKit Docker daemon that fails on `RUN --mount`.

####################################
# ---------- builder --------------
####################################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# uv environment configuration
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Optional build-time flag: set to "true" to include dev dependencies
ARG INSTALL_DEV=false

# Optional build-time flag: set to "true" to include PDF parsing dependencies/tools
ARG INSTALL_PDF_PARSING=false

# The environment is built under the uid the runtime stages run as, so copying
# it needs no `--chown` pass over ~500 MB of files and the runtime user can
# still install into it, e.g. while debugging inside a running container.
RUN useradd --system --uid 1000 --create-home --shell /bin/bash standard_user \
    && install -d -o standard_user -g standard_user /opt/venv /app

WORKDIR /app

# Copy dependency metadata only
COPY --chown=standard_user:standard_user pyproject.toml uv.lock* ./

USER standard_user

# Resolve & install deps into /opt/venv with --frozen for reproducibility.
# Every locked distribution ships a wheel, so no compiler or -dev headers are
# installed here; a dependency without a wheel would fail this step and needs
# build-essential plus its own headers added back.
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        if [ "$INSTALL_PDF_PARSING" = "true" ]; then \
            uv sync --locked --dev --group pdf_parsing; \
        else \
            uv sync --locked --dev; \
        fi; \
    else \
        if [ "$INSTALL_PDF_PARSING" = "true" ]; then \
            uv sync --locked --no-dev --group pdf_parsing; \
        else \
            uv sync --locked --no-dev; \
        fi; \
    fi

####################################
# ---------- runtime base ---------
####################################
FROM python:3.12-slim-bookworm AS runtime-base

ARG INSTALL_PDF_PARSING=false

# Python environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimum runtime OS libraries and non-root user setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libproj25 \
    libgdal32 \
    curl \
    && if [ "$INSTALL_PDF_PARSING" = "true" ]; then \
        apt-get install -y --no-install-recommends poppler-utils; \
    fi \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --create-home --shell /bin/bash standard_user \
    && install -d -o standard_user -g standard_user /app/staticfiles /opt/venv

# Virtual environment first on PATH
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Already owned by uid 1000 in the builder, so no ownership rewrite here.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

USER standard_user

# Expose & configure the port
EXPOSE 8000
ENV PORT=8000
ENV DJANGO_WSGI=brit.wsgi:application

# Basic health-check (30 s interval, 5 s timeout)
HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command (production-ready with Gunicorn)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers ${WORKERS:-3} $DJANGO_WSGI"]

####################################
# ---------- dev ------------------
####################################
# Target used by compose.yml, which bind-mounts the checkout at /app. Carrying
# no source layer keeps this image valid across source edits, so local builds
# stay cache hits until a dependency input changes.
FROM runtime-base AS dev

####################################
# ---------- runtime --------------
####################################
# Default target: self-contained image for Heroku and any other deployment.
FROM runtime-base AS runtime

COPY --chown=standard_user:standard_user . /app
