"""Automated validation suite for Lab3 Dockerfiles, Compose, and Kubernetes manifests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

LAB3_ROOT = Path(__file__).resolve().parent.parent
LAB2_ROOT = LAB3_ROOT.parent / "Lab2"


def test_all_eight_dockerfiles_and_dockerignores_exist_and_use_non_root() -> None:
    dockerfile_paths = [
        LAB2_ROOT / "services" / "auth-service" / "Dockerfile",
        LAB2_ROOT / "services" / "user-service" / "Dockerfile",
        LAB2_ROOT / "services" / "product-service" / "Dockerfile",
        LAB2_ROOT / "services" / "order-service" / "Dockerfile",
        LAB2_ROOT / "services" / "payment-service" / "Dockerfile",
        LAB2_ROOT / "services" / "notification-service" / "Dockerfile",
        LAB2_ROOT / "gateway" / "Dockerfile",
        LAB2_ROOT / "frontend" / "Dockerfile",
    ]
    for path in dockerfile_paths:
        assert path.is_file(), f"Missing Dockerfile: {path}"
        assert (path.parent / ".dockerignore").is_file(), f"Missing .dockerignore near {path}"
        text = path.read_text(encoding="utf-8")
        assert "EXPOSE " in text
        assert ("USER appuser" in text) or ("nginx-unprivileged" in text), f"Non-root user required in {path}"


def test_lab3_compose_isolates_internal_services_and_exposes_only_frontend() -> None:
    compose_file = LAB3_ROOT / "docker" / "docker-compose.yml"
    data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    services = data["services"]
    assert len(services) == 10

    host_exposed = [name for name, cfg in services.items() if "ports" in cfg]
    assert host_exposed == ["frontend"]
    assert services["frontend"]["ports"] == ["8080:8080"]

    for name, cfg in services.items():
        assert "healthcheck" in cfg, f"Missing healthcheck in compose service {name}"
        if name != "frontend":
            assert "expose" in cfg, f"Internal service {name} should declare expose"


def test_kustomize_renders_valid_isolated_kubernetes_manifests() -> None:
    assert shutil.which("kubectl"), "kubectl binary is required for kustomize validation"
    proc = subprocess.run(
        ["kubectl", "kustomize", str(LAB3_ROOT / "k8s")],
        capture_output=True,
        text=True,
        check=True,
    )
    docs = [doc for doc in yaml.safe_load_all(proc.stdout) if doc]
    by_kind: dict[str, list[dict]] = {}
    for doc in docs:
        by_kind.setdefault(doc["kind"], []).append(doc)

    assert len(by_kind["Namespace"]) == 1
    assert by_kind["Namespace"][0]["metadata"]["name"] == "shopflow"
    assert len(by_kind["Secret"]) == 1
    assert len(by_kind["PersistentVolumeClaim"]) == 1
    assert len(by_kind["HorizontalPodAutoscaler"]) == 1

    # Verify ConfigMap uses Kubernetes DNS names and never localhost
    app_cm = next(cm for cm in by_kind["ConfigMap"] if cm["metadata"]["name"] == "shopflow-config")
    for key, val in app_cm["data"].items():
        assert "localhost" not in val and "127.0.0.1" not in val, f"{key} must not use localhost"

    # Verify all 10 Deployments have probes and resource limits
    deployments = by_kind["Deployment"]
    assert len(deployments) == 10
    app_names = {
        "auth-service",
        "user-service",
        "product-service",
        "order-service",
        "payment-service",
        "notification-service",
        "api-gateway",
        "frontend",
    }
    for dep in deployments:
        name = dep["metadata"]["name"]
        container = dep["spec"]["template"]["spec"]["containers"][0]
        assert "livenessProbe" in container, f"Missing livenessProbe in {name}"
        assert "readinessProbe" in container, f"Missing readinessProbe in {name}"
        assert "requests" in container["resources"], f"Missing resource requests in {name}"
        assert "limits" in container["resources"], f"Missing resource limits in {name}"
        if name in app_names:
            sec = container.get("securityContext", {})
            assert sec.get("runAsNonRoot") is True, f"{name} must enforce runAsNonRoot"

    # Verify Services: only frontend is NodePort, all 9 others are ClusterIP
    services = by_kind["Service"]
    assert len(services) == 10
    nodeports = [svc["metadata"]["name"] for svc in services if svc["spec"]["type"] == "NodePort"]
    assert nodeports == ["frontend"]
    for svc in services:
        if svc["metadata"]["name"] != "frontend":
            assert svc["spec"]["type"] == "ClusterIP"
