# Use the official Python image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY poetry.lock pyproject.toml ./

# Install Poetry
RUN pip install poetry

# Install Poetry and dependencies
RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install --no-dev

# Install the system-level MySQL client
RUN apt-get update && apt-get install -y default-mysql-client

# Copy the rest of the application code
COPY . .

# Copy the config directory to the app
COPY config ./config  

# Expose the FastAPI port
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "fast:app", "--host", "0.0.0.0", "--port", "8000"]
