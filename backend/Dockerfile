# ── Stage 1: builder — install deps into a virtual env ────────────
FROM python:3.12-slim AS builder

# Install build tools needed to compile wheels (e.g. pandas, qrcode)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a virtualenv so we can copy it cleanly into the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies — cached layer that only re-builds when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime — minimal image with only what's needed ──────
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser --no-create-home appuser

# Copy the pre-built virtualenv from the builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory owned by the non-root user
WORKDIR /app
RUN mkdir -p /app/data /app/qr_cache && chown -R appuser:appuser /app
USER appuser

# Copy application source
COPY --chown=appuser:appuser . /app

# Expose the API port
EXPOSE 8001

# Healthcheck — hits the OpenAPI docs endpoint (lightweight, no auth needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health', timeout=3).read()" || exit 1

# Run with uvicorn (no reload in production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--proxy-headers"]
