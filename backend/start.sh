#!/bin/bash 
# Log startup message
echo "=== Starting CareOutreach Free Tier Deployment ==="
  # 1\. Start the Celery background worker
echo "Starting Celery Worker..." celery -A app.workers.celery\_app worker --loglevel=info &amp;
# 2\. Start Celery Beat for periodic tasks (15-min escalation timeout &amp; stuck task recovery)
echo "Starting Celery Beat..." celery -A app.workers.celery\_app beat --loglevel=info &amp;
# 3\. Start FastAPI Uvicorn Web Server in the foreground 
echo "Starting FastAPI Uvicorn Server on port ${PORT:-8000}..." exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}