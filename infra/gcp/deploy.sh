#!/usr/bin/env bash
set -euo pipefail

# Simple Cloud Run deploy helper for Alfred API

usage() {
  cat <<'EOF'
Usage: bash infra/gcp/deploy.sh [-p PROJECT] [-r REGION] [-s SERVICE] [-R REPOSITORY] [-i IMAGE] [-e ENV_FILE]

Options:
  -p PROJECT       GCP project ID (default: current gcloud config)
  -r REGION        Region for Artifact Registry and Cloud Run (default: us-central1)
  -s SERVICE       Cloud Run service name (default: alfred-api)
  -R REPOSITORY    Artifact Registry repo name (default: alfred)
  -i IMAGE         Image name within the repo (default: alfred-api)
  -e ENV_FILE      Optional .env file to apply as Cloud Run environment variables

Examples:
  bash infra/gcp/deploy.sh
  bash infra/gcp/deploy.sh -p my-proj -r us-central1 -s alfred-api -R alfred -i alfred-api -e alfred/.env
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PROJECT="$(gcloud config get-value project 2>/dev/null || echo "")"
REGION="us-central1"
SERVICE="alfred-api"
REPOSITORY="alfred"
IMAGE="alfred-api"
ENV_FILE=""

while getopts ":p:r:s:R:i:e:h" opt; do
  case $opt in
    p) PROJECT="$OPTARG" ;;
    r) REGION="$OPTARG" ;;
    s) SERVICE="$OPTARG" ;;
    R) REPOSITORY="$OPTARG" ;;
    i) IMAGE="$OPTARG" ;;
    e) ENV_FILE="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  echo "[!] No GCP project set. Use -p or 'gcloud config set project <ID>'" >&2
  exit 1
fi

echo "[i] Project     : $PROJECT"
echo "[i] Region      : $REGION"
echo "[i] Repository  : $REPOSITORY"
echo "[i] Image       : $IMAGE"
echo "[i] Service     : $SERVICE"
if [[ -n "$ENV_FILE" ]]; then
  echo "[i] Env file    : $ENV_FILE"
fi

echo "[i] Enabling required APIs (may be no-ops)"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project "$PROJECT"

echo "[i] Ensuring Artifact Registry '$REPOSITORY' exists in $REGION"
if ! gcloud artifacts repositories describe "$REPOSITORY" \
  --location="$REGION" \
  --project="$PROJECT" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Alfred images" \
    --project="$PROJECT"
else
  echo "[i] Repository already exists"
fi

echo "[i] Building and deploying via Cloud Build"
gcloud builds submit "${ROOT_DIR}" \
  --config "${ROOT_DIR}/infra/gcp/cloudbuild.yaml" \
  --project "$PROJECT" \
  --substitutions=_REGION="$REGION",_SERVICE="$SERVICE",_REPOSITORY="$REPOSITORY",_IMAGE="$IMAGE"

echo "[i] Fetching service URL"
SERVICE_URL=$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --format='value(status.url)' || true)

if [[ -n "$SERVICE_URL" ]]; then
  echo "[i] Cloud Run URL: $SERVICE_URL"
else
  echo "[!] Could not fetch service URL (service may still be provisioning)." >&2
fi

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[!] Env file not found: $ENV_FILE" >&2
    exit 1
  fi
  echo "[i] Applying environment variables from $ENV_FILE"
  # Apply variables one-by-one to avoid issues with commas in values.
  while IFS= read -r line || [[ -n "$line" ]]; do
    # skip comments and empty lines
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    # Only process KEY=VALUE lines
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      key="${line%%=*}"
      val="${line#*=}"
      # Trim quotes but keep content
      val="${val%\r}"
      echo "    -> $key"
      gcloud run services update "$SERVICE" \
        --region "$REGION" \
        --project "$PROJECT" \
        --set-env-vars "${key}=${val}"
    fi
  done < "$ENV_FILE"

  echo "[i] Env vars applied. Latest URL:"
  gcloud run services describe "$SERVICE" \
    --region "$REGION" \
    --project "$PROJECT" \
    --format='value(status.url)'
fi

echo "[✓] Done. Open the service URL above or run:\n    gcloud run services describe $SERVICE --region $REGION --project $PROJECT --format='value(status.url)'"
