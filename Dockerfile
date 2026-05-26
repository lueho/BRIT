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

# System build dependencies (kept only in this stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libproj-dev \
    libgdal-dev \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency metadata only
COPY pyproject.toml uv.lock* ./

# Resolve & install deps into .venv with --frozen for reproducibility (without BuildKit cache)
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

COPY . .

####################################
# ---------- runtime --------------
####################################
FROM python:3.12-slim-bookworm

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
    && install -d -o standard_user -g standard_user /app/staticfiles

# Virtual environment first on PATH
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the virtual environment and project from builder with proper ownership
COPY --from=builder --chown=standard_user:standard_user /opt/venv /opt/venv
COPY --from=builder --chown=standard_user:standard_user /app /app

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
