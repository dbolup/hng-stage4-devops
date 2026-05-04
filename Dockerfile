FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Create log directory
RUN mkdir -p /var/log/app && chown appuser:appuser /var/log/app

# Copy app files
COPY app/ .

# Switch to non-root user
USER appuser

# Drop all capabilities
# (handled in docker-compose)

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/healthz')" || exit 1

CMD ["python", "main.py"]
