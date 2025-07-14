FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PUID=99
ENV PGID=100

# Don't create user here - let entrypoint handle it dynamically

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py index.html ./

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories and set permissions
RUN mkdir -p data output textures/blocks

# Copy data files
COPY data/ ./data/

# Copy output directory
COPY output/ ./output/

# Copy pack icon
COPY pack_icon.png ./pack_icon.png

# Copy textures
COPY textures/ ./textures/

# Don't fix ownership here - let entrypoint handle it
# This ensures it works with mounted volumes

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5096/ || exit 1

# Expose port
EXPOSE 5096

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5096", "--timeout", "120", "--workers", "1", "--max-requests", "1000", "--max-requests-jitter", "100", "app:app"]