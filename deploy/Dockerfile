
# Stage 1: Builder - Install dependencies
FROM --platform=$TARGETPLATFORM python:3.12-slim as builder

# multi arch build
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG BUILDARCH
ARG TARGETARCH
RUN echo "I am running on $BUILDPLATFORM $BUILDARCH, building for $TARGETPLATFORM $TARGETARCH"

# Set working directory
WORKDIR /app
# Copy dependency definition files
COPY requirements.txt pyproject.toml ./

# Copy the application source code
COPY ./* ./

# Install dependencies using requirements.txt
# This leverages Docker's layer caching, so dependencies are only re-installed
# if the requirements.txt changes.
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final image - Create the production image
FROM --platform=$TARGETPLATFORM python:3.12-slim

# Set working directory
WORKDIR /app
# Copy the application source code
COPY ./* ./

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Run the main server with http transport for containerized environments
CMD ["python", "-m", "main_server", "--transport", "http", "--allow-write", "--host", "0.0.0.0", "--port", "8000"]

# how to run
# docker run -e ACCESS_KEY_ID=<your-access-key-id> -e ACCESS_KEY_SECRET=<your-access-key-secret> -p 8000:8000 ack-mcp-server:1.0 python -m main_server --transport http --allow-write --host 0.0.0.0 --port 8000