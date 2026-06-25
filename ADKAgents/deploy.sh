gcloud builds submit --tag us-central1-docker.pkg.dev/edb-hack2026-team9/agent-repo/agent:latest

gcloud run deploy agent-service --image us-central1-docker.pkg.dev/edb-hack2026-team9/agent-repo/agent:latest --platform managed --region us-central1 --allow-unauthenticated --min-instances=1 --max-instances=1

