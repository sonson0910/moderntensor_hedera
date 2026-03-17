# ─────────────────────────────────────────────────────────────
# ModernTensor Hedera — Production Docker Image
# Multi-stage build for minimal attack surface & small image
# ─────────────────────────────────────────────────────────────

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim AS runtime

# Security: non-root user
RUN groupadd -r mtensor && useradd -r -g mtensor -d /app mtensor

WORKDIR /app

# Copy pre-built deps from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY sdk/ ./sdk/
COPY pyproject.toml .
COPY requirements.txt .

# Install the package itself
RUN pip install --no-cache-dir -e . 2>/dev/null || true

# Expose Prometheus metrics port + FastAPI
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import sdk; print('OK')" || exit 1

# Switch to non-root
USER mtensor

# Default: run the FastAPI dashboard
CMD ["uvicorn", "sdk.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
