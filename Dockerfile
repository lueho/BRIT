# syntax=docker/dockerfile:1

####################################
# ---------- builder --------------
####################################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# uv environment configuration
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Optional build-time flag: set to "true" to include dev dependencies
ARG INSTALL_DEV=false

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

# Resolve & install deps into .venv with --frozen for reproducibility
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_DEV" = "true" ]; then \
    uv sync --locked --dev; \
    else \
    uv sync --locked --no-dev; \
    fi

COPY . .

####################################
# ---------- runtime --------------
####################################
FROM python:3.12-slim-bookworm

# Python environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimum runtime OS libraries (removed gdal-bin to save ~20MB if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libproj25 \
    libgdal32 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user & static-files directory
RUN useradd --system --uid 1000 --create-home --shell /bin/bash standard_user \
    && install -d -o standard_user -g standard_user /app/staticfiles

# Virtual environment first on PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the virtual environment and project metadata from builder with proper ownership
COPY --from=builder --chown=standard_user:standard_user /app /app

WORKDIR /app

# Copy the application source code with proper ownership
COPY --chown=standard_user:standard_user . .

USER standard_user

# Ensure shell helpers are executable (optional)
RUN find . -maxdepth 1 -name "*.sh" -exec chmod +x {} +

# Expose & configure the port
EXPOSE 8000
ENV PORT=8000
ENV DJANGO_WSGI=brit.wsgi:application

# Basic health-check (30 s interval, 5 s timeout)
HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command (production-ready with Gunicorn)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:8000 --workers 3 $DJANGO_WSGI"]
