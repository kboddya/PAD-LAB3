#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="shopflow"

echo "=== 1. Initial cluster state ==="
kubectl get deployments,pods,services -n "${NAMESPACE}"

echo ""
echo "=== 2. Horizontal scaling demonstration (order-service -> 4 replicas) ==="
kubectl scale deployment order-service -n "${NAMESPACE}" --replicas=4
kubectl rollout status deployment/order-service -n "${NAMESPACE}" --timeout=90s
kubectl get pods -n "${NAMESPACE}" -l app=order-service

echo ""
echo "=== 3. Self-healing demonstration (deleting one order-service Pod) ==="
TARGET_POD="$(kubectl get pods -n "${NAMESPACE}" -l app=order-service -o jsonpath='{.items[0].metadata.name}')"
echo "Deleting pod: ${TARGET_POD}"
kubectl delete pod "${TARGET_POD}" -n "${NAMESPACE}"
kubectl rollout status deployment/order-service -n "${NAMESPACE}" --timeout=90s
kubectl get pods -n "${NAMESPACE}" -l app=order-service

echo ""
echo "=== 4. Scaling back to 2 replicas ==="
kubectl scale deployment order-service -n "${NAMESPACE}" --replicas=2
kubectl rollout status deployment/order-service -n "${NAMESPACE}" --timeout=90s

echo ""
echo "=== 5. Sample logs and Frontend API check ==="
GW_POD="$(kubectl get pods -n "${NAMESPACE}" -l app=api-gateway -o jsonpath='{.items[0].metadata.name}')"
kubectl logs -n "${NAMESPACE}" "${GW_POD}" --tail=15
