#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB3_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[1/5] Checking Minikube cluster..."
if ! minikube status >/dev/null 2>&1; then
  minikube start --cpus=2 --memory=4096
fi

echo "[2/5] Building all 8 ShopFlow images inside Minikube Docker daemon..."
"${LAB3_DIR}/docker/build-images.sh" --minikube

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
echo "ShopFlow UI URL: $(minikube service frontend -n shopflow --url)"
