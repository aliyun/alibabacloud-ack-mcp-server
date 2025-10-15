
# Stage 1: Builder - Install dependencies
FROM --platform=$TARGETPLATFORM python:3.11-slim as builder

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
FROM --platform=$TARGETPLATFORM python:3.11-slim

# multi arch build
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG BUILDARCH
ARG TARGETARCH

# Set working directory
WORKDIR /app
# Copy the application source code
COPY ./* ./

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install kubectl and other required tools
# Install wget and other dependencies needed for kubectl
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl with multi-arch support
RUN set -ex; \
    # Determine architecture for kubectl download
    case "${TARGETARCH}" in \
        amd64) KUBECTL_ARCH="amd64" ;; \
        arm64) KUBECTL_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac; \
    # Download and install kubectl
    KUBECTL_VERSION=$(wget -qO- https://dl.k8s.io/release/stable.txt) && \
    wget -O kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${KUBECTL_ARCH}/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    # Verify kubectl installation
    kubectl version --client

# Create a non-root user for security
# Create user with home directory and proper permissions
RUN groupadd -r -g 1001 appuser && \
    useradd -r -u 1001 -g appuser -m -d /home/appuser appuser && \
    mkdir -p /home/appuser/.kube /home/appuser/.cache && \
    chown -R appuser:appuser /app /home/appuser

# Ensure kubectl is executable by appuser
# kubectl is installed in /usr/local/bin which is already in PATH
# No additional permissions needed as it's already chmod +x in previous step

USER appuser

# Set environment variables for kubectl cache and config
ENV KUBECONFIG=/home/appuser/.kube/config
ENV KUBECTL_CACHE_DIR=/home/appuser/.cache/kubectl

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