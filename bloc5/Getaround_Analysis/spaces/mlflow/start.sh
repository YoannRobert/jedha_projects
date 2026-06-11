#!/bin/bash
set -e

echo ">>> Creating basic_auth.ini ..."
sed \
  -e "s/PLACEHOLDER_ADMIN_USERNAME/${ADMIN_USERNAME}/g" \
  -e "s/PLACEHOLDER_ADMIN_PASSWORD/${ADMIN_PASSWORD}/g" \
  /app/basic_auth.ini.template > /app/basic_auth.ini

echo ">>> Launching MLflow..."
export MLFLOW_AUTH_CONFIG_PATH=/app/basic_auth.ini
mlflow server \
  --app-name basic-auth \
  --host 0.0.0.0 \
  --port ${PORT} \
  --workers 1 \
  --allowed-hosts ${HF_MLFLOW_SPACE_URL_WITHOUT_HTTP} \
  --cors-allowed-origins "https://${HF_MLFLOW_SPACE_URL_WITHOUT_HTTP}" \
  --backend-store-uri "postgresql://${NEON_USERNAME}:${NEON_PASSWORD}@${NEON_HOST}/neondb?sslmode=require" \
  --default-artifact-root "${ARTIFACT_STORE_URI}" &

MLFLOW_PID=$!

echo ">>> Waiting for MLflow to start ..."
until curl -s -f \
  -H "Host: ${HF_MLFLOW_SPACE_URL_WITHOUT_HTTP}" \
  -H "Content-Type: application/json" \
  -u "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" \
  http://localhost:${PORT}/api/2.0/mlflow/experiments/search \
  -d '{"max_results": 1}' > /dev/null 2>&1; do
  echo "  Waiting..."
  sleep 3
done || true
echo ">>> MLflow is ready."

echo ">>> Initialisation completed."
wait $MLFLOW_PID