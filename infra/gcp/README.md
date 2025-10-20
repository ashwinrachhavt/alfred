Google Cloud Run Deployment (Docker)

Overview
- Build a Docker image for the Alfred API and deploy to Cloud Run via Cloud Build and Artifact Registry.
- This keeps infra simple and serverless (no VM management).

Prerequisites
- gcloud SDK installed and authenticated: gcloud auth login
- Set your project and region:
  - gcloud config set project YOUR_PROJECT_ID
  - gcloud config set run/region us-central1
- Enable required APIs:
  - gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

Create Artifact Registry
```bash
REGION=us-central1
REPO=alfred
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Alfred images"
```

Build and Deploy with Cloud Build
```bash
# From anywhere (script locates repo root automatically)
bash infra/gcp/deploy.sh
# Or specify project/region/env file:
bash infra/gcp/deploy.sh -p YOUR_PROJECT -r us-central1 -s alfred-api -R alfred -i alfred-api -e apps/alfred/.env
```

On success, Cloud Run prints the service URL.

Environment Variables
- Copy apps/alfred/.env.example to apps/alfred/.env locally for reference, but do NOT bake secrets into the image.
- Set env vars on the Cloud Run service (or use Secret Manager):
```bash
gcloud run services update alfred-api \
  --region=us-central1 \
  --set-env-vars=OPENAI_API_KEY=... \
  --set-env-vars=QDRANT_URL=... \
  --set-env-vars=QDRANT_API_KEY=... \
  --set-env-vars=NOTION_TOKEN=... \
  --set-env-vars=CORS_ALLOW_ORIGINS='["*"]'
```

Notes
- The container listens on $PORT (Cloud Run sets it); default is 8080.
- If you use Google OAuth flows (Gmail/Calendar), add your Cloud Run URL to the OAuth client’s Authorized redirect URIs (e.g., https://SERVICE-URL/api/gmail/oauth/callback).
- For persistent token storage (e.g., TOKEN_STORE_DIR), prefer Secret Manager or a database. Cloud Run’s filesystem is ephemeral.

Local Test
```bash
docker build -f apps/alfred/Dockerfile -t alfred-api:local .
docker run -p 8080:8080 --env-file apps/alfred/.env alfred-api:local
# Open http://localhost:8080/docs
```

Troubleshooting
- 403 on deploy: ensure you have IAM roles for Cloud Build and Cloud Run Admin.
- Empty web search: confirm provider packages/keys present and env vars are set on the service.
- OAuth redirect mismatch: update GOOGLE_REDIRECT_URI and your OAuth client in Google Cloud Console.
