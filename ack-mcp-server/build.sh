#!/bin/zsh

# This script builds the Docker image for the MCP server and pushes it to a specified registry.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# You can change these variables
IMAGE_NAME="k8s-mcp-server"
VERSION="latest"
# Default to Aliyun Hangzhou registry, change if you use another one.
REGISTRY="registry.cn-hangzhou.aliyuncs.com/your-namespace"


# --- Script Logic ---

# 1. Build the Docker image
echo "Building Docker image: ${IMAGE_NAME}:${VERSION}..."
docker build --platform linux/amd64 -t "${IMAGE_NAME}:${VERSION}" .
echo "Image built successfully."

# 2. Tag the image for the registry
echo "Tagging image for registry: ${REGISTRY}/${IMAGE_NAME}:${VERSION}..."
docker tag "${IMAGE_NAME}:${VERSION}" "${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo "Image tagged successfully."

# 3. Log in to the Docker registry
# Make sure you have credentials configured for this step.
echo "Logging in to registry: ${REGISTRY}..."
docker login "${REGISTRY}"
echo "Login successful."

# 4. Push the image to the registry
echo "Pushing image to registry: ${REGISTRY}/${IMAGE_NAME}:${VERSION}..."
docker push "${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo "Image pushed successfully."

echo -e "\nBuild and push process completed."