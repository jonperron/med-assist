# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy the dependencies file to the working directory
COPY poetry.lock pyproject.toml ./

# Install any needed packages specified in pyproject.toml
RUN poetry install --no-dev --no-root

# Copy the content of the local src directory to the working directory
COPY ./app /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV PYTHONPATH=/app

# Run app.main.py when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]