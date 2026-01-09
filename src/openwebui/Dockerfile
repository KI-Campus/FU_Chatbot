FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.0

# Copy pyproject.toml and poetry.lock (if exists)
COPY pyproject.toml poetry.lock* ./

# Install dependencies using poetry (including api and dev groups)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --with api

# Copy all source code
COPY . .

# Create config if it doesn't exist from the COPY above
RUN test -d /app/config || mkdir -p /app/config

# Expose port
EXPOSE 8001

# Run the OpenWebUI API
CMD ["uvicorn", "src.openwebui.openwebui_api_llm:app", "--host", "0.0.0.0", "--port", "8001"]
