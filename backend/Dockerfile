# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the dependencies file to the working directory
COPY uv.lock pyproject.toml README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the content of the local src directory to the working directory
COPY ./app ./app
COPY ./models ./models

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run app.main.py when the container launches
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
