# 11 - Deployment Specification

## docker-compose services
- postgres:16-alpine (port 5432, PVC pgdata)
- redis:7-alpine (port 6379, appendonly)
- qdrant:latest (ports 6333/6334, PVC)
- backend: FastAPI on 8000, env: DATABASE_URL, REDIS_URL, QDRANT_URL
- worker: python -m flowforge.worker, same env
- frontend: Vite dev on 5173, env: VITE_API_URL

## Dockerfile.backend
- python:3.12-slim, WORKDIR /app, install deps, CMD uvicorn

## Dockerfile.frontend
- Multi-stage: node:20-alpine builds, nginx:alpine serves
- nginx proxies /api and /ws to backend

## Kubernetes (k8s/)
- namespace.yaml: flowforge namespace
- backend-deployment: 2 replicas, 250m-1000m CPU, 512Mi-1Gi mem, /health probe
- worker-deployment: 2 replicas, 500m-2000m CPU, 512Mi-2Gi mem, health port 8081
- frontend-deployment: 2 replicas, 100m CPU, 128Mi mem
- redis.yaml: 1 replica, PVC 5Gi
- postgres.yaml: 1 replica, PVC 20Gi
- qdrant.yaml: 1 replica, PVC 10Gi
- hpa.yaml: workers min 2 max 50, CPU 70%, scale up +5/60s, down -2/120s
- ingress.yaml: flowforge.local, /api->backend, /ws->backend, /->frontend

## Minikube
minikube start --cpus=4 --memory=8192
minikube addons enable ingress
kubectl apply all manifests
Add minikube IP to /etc/hosts as flowforge.local

## Config
ConfigMap: REDIS_URL, QDRANT_URL, LOG_LEVEL, WORKER_HEALTH_PORT, GRAPH_CACHE_TTL
Secrets: DATABASE_URL, JWT_SECRET (use sealed-secrets in prod)
