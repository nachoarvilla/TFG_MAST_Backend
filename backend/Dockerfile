# We use a lightweight image of Python 3.11
FROM python:3.11-slim

# Working directory inside the container
WORKDIR /app

# Copy requirements.txt first to leverage Docker's cache
COPY requirements.txt .

# Install the necessary libraries
RUN pip install --no-cache-dir -r requirements.txt

# Copy code to the container
COPY . .

# Command to start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]