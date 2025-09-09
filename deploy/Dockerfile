# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install uv for package management
RUN pip install uv

# Copy dependency definition files
COPY pyproject.toml uv.lock* ./

# Install dependencies into a separate layer.
# This leverages Docker's layer caching, so dependencies are only re-installed
# if the lock file or pyproject.toml changes.
RUN uv pip install --system --no-cache -r pyproject.toml --no-deps

# Stage 2: Final image - Create the production image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY app ./app

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
# The -m flag runs the module as a script
CMD ["python", "-m", "app.main"]