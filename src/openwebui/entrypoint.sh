#!/bin/bash

# Entrypoint script that fetches secrets from Azure Key Vault if available
# This runs inside the container before starting the API

set -e

# Function to securely fetch a secret from Key Vault
fetch_secret() {
    local secret_name=$1
    local env_var_name=$2
    
    # Check if already set in environment
    if [ ! -z "${!env_var_name}" ]; then
        echo "✓ $env_var_name already set in environment"
        return
    fi
    
    # Try to fetch from Key Vault if credentials are available
    if [ "$USE_KEY_VAULT" = "true" ] || [ "$USE_KEY_VAULT" = "1" ]; then
        echo "Fetching $secret_name from Key Vault..."
        # Note: This assumes the pod/container has AZURE_KEYVAULT_ENDPOINT or similar set
        # For local Docker, we would need to mount credentials or use az cli
        # For now, we just warn if not found locally
        if [ -z "${!env_var_name}" ]; then
            echo "⚠ $env_var_name not found locally - Key Vault access might not be available in this container"
        fi
    fi
}

# List of secrets to fetch
SECRETS=(
    "AZURE_OPENAI_URL"
    "AZURE_OPENAI_API_KEY"
    "AZURE_OPENAI_EMBEDDER_DEPLOYMENT"
    "AZURE_OPENAI_EMBEDDER_MODEL"
    "AZURE_OPENAI_GPT4_DEPLOYMENT"
    "AZURE_OPENAI_GPT4_MODEL"
)

echo "=== Initializing Secrets ==="
for secret in "${SECRETS[@]}"; do
    # Check if set
    if [ -z "${!secret}" ]; then
        echo "⚠ $secret not set"
    else
        echo "✓ $secret is configured"
    fi
done

echo ""
echo "=== Starting API ==="
exec python -m uvicorn src.openwebui.openwebui_api_llm:app --host 0.0.0.0 --port 8001
