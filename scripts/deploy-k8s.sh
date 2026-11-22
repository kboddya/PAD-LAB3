#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB3_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

START_K8S=false
if [[ "${1:-}" == "--start-k8s" ]]; then
  START_K8S=true
fi

echo "[1/5] Checking Kubernetes cluster connectivity..."
if ! kubectl cluster-info >/dev/null 2>&1; then
  if [[ "${START_K8S}" == "true" ]] && command -v orb >/dev/null 2>&1; then
    echo "Starting OrbStack Kubernetes..."
    orb start k8s
  else
    echo "ERROR: Kubernetes cluster is not reachable."
    if command -v orb >/dev/null 2>&1; then
      echo "Hint: OrbStack is installed. Run 'orb start k8s' (or re-run this script with '--start-k8s')."
    else
      echo "Hint: Enable Kubernetes in Docker Desktop / OrbStack or start Minikube."
    fi
    exit 1
  fi
fi

echo "[2/5] Building all 8 ShopFlow Docker images..."
"${LAB3_DIR}/docker/build-images.sh"

echo "[3/5] Applying Kubernetes manifests via Kustomize..."
kubectl apply -k "${LAB3_DIR}/k8s"

echo "[4/5] Waiting for infrastructure (PostgreSQL & RabbitMQ)..."
kubectl wait --namespace shopflow --for=condition=available deployment/postgres --timeout=120s
kubectl wait --namespace shopflow --for=condition=available deployment/rabbitmq --timeout=120s

echo "[5/5] Waiting for all microservices, API Gateway and Frontend..."
for deploy in auth-service user-service product-service order-service payment-service notification-service api-gateway frontend; do
  kubectl wait --namespace shopflow --for=condition=available "deployment/${deploy}" --timeout=120s
done

echo ""
kubectl get pods,svc,deployments -n shopflow
echo ""
echo "ShopFlow UI (NodePort): http://localhost:30080"
echo "Optional port-forward:  kubectl port-forward -n shopflow svc/frontend 8080:8080"
