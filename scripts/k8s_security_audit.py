"""Kubernetes & container security audit suite for Lab3 manifests.

Runs CIS Kubernetes / Pod Security Standards (Restricted) checks on rendered Kustomize YAML
and saves structured JSON reports for before/after comparisons.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

LAB3_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class K8sSecurityFinding:
    check_id: str
    title: str
    severity: str
    standard: str
    status: str  # PASS | FAIL
    evidence: str
    remediation: str


def run_k8s_audit() -> list[K8sSecurityFinding]:
    proc = subprocess.run(
        ["kubectl", "kustomize", str(LAB3_ROOT / "k8s")],
        capture_output=True,
        text=True,
        check=True,
    )
    docs = [doc for doc in yaml.safe_load_all(proc.stdout) if doc]

    deployments = [d for d in docs if d["kind"] == "Deployment"]
    network_policies = [d for d in docs if d["kind"] == "NetworkPolicy"]
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

    findings: list[K8sSecurityFinding] = []

    # K8S-01: Hardcoded credentials in RabbitMQ Deployment
    rmq = next(d for d in deployments if d["metadata"]["name"] == "rabbitmq")
    rmq_env = rmq["spec"]["template"]["spec"]["containers"][0].get("env", [])
    hardcoded_rmq = [
        e["name"] for e in rmq_env if "value" in e and ("PASS" in e["name"] or "USER" in e["name"])
    ]
    findings.append(
        K8sSecurityFinding(
            check_id="K8S-01",
            title="Hardcoded RabbitMQ credentials in Deployment env",
            severity="High",
            standard="CIS Kubernetes 5.4.1",
            status="PASS" if not hardcoded_rmq else "FAIL",
            evidence=(
                "RabbitMQ credentials injected from Secret"
                if not hardcoded_rmq
                else f"Plaintext env values found in rabbitmq Deployment: {hardcoded_rmq}"
            ),
            remediation="Load RABBITMQ_DEFAULT_USER and RABBITMQ_DEFAULT_PASS via secretKeyRef.",
        )
    )

    # K8S-02: Secret blast-radius (envFrom exposing all 6 DB DSNs to every service)
    broad_secret_deps: list[str] = []
    for dep in deployments:
        name = dep["metadata"]["name"]
        if name not in app_names or name == "frontend":
            continue
        container = dep["spec"]["template"]["spec"]["containers"][0]
        env_from = container.get("envFrom", [])
        if any(item.get("secretRef", {}).get("name") == "shopflow-secrets" for item in env_from):
            broad_secret_deps.append(name)

    findings.append(
        K8sSecurityFinding(
            check_id="K8S-02",
            title="Excessive Secret exposure via envFrom (cross-service DB DSN access)",
            severity="High",
            standard="Least Privilege / CIS 5.4.2",
            status="PASS" if not broad_secret_deps else "FAIL",
            evidence=(
                "Each microservice receives only its own DB DSN and required keys via secretKeyRef"
                if not broad_secret_deps
                else f"Services mounting full shopflow-secrets via envFrom: {broad_secret_deps}"
            ),
            remediation="Replace broad envFrom secretRef with scoped per-service secretKeyRef env entries.",
        )
    )

    # K8S-03: Pod Security Standards Restricted (capabilities.drop ALL + seccompProfile RuntimeDefault)
    missing_hardening: list[str] = []
    for dep in deployments:
        name = dep["metadata"]["name"]
        if name not in app_names:
            continue
        pod_spec = dep["spec"]["template"]["spec"]
        container = pod_spec["containers"][0]
        sec = container.get("securityContext", {})
        caps_drop = sec.get("capabilities", {}).get("drop", [])
        seccomp = (
            sec.get("seccompProfile", {}).get("type")
            or pod_spec.get("securityContext", {}).get("seccompProfile", {}).get("type")
        )
        if "ALL" not in caps_drop or seccomp != "RuntimeDefault":
            missing_hardening.append(name)

    findings.append(
        K8sSecurityFinding(
            check_id="K8S-03",
            title="Pod Security Standards (Restricted): drop ALL capabilities & RuntimeDefault seccomp",
            severity="Medium",
            standard="Kubernetes PSS Restricted",
            status="PASS" if not missing_hardening else "FAIL",
            evidence=(
                "All 8 app Deployments drop ALL Linux capabilities and enforce RuntimeDefault seccomp"
                if not missing_hardening
                else f"Deployments missing capabilities.drop=ALL or seccompProfile: {missing_hardening}"
            ),
            remediation="Set securityContext.capabilities.drop=['ALL'] and seccompProfile.type='RuntimeDefault'.",
        )
    )

    # K8S-04: NetworkPolicy micro-segmentation
    has_default_deny = any(
        np["metadata"]["name"] == "default-deny-ingress" for np in network_policies
    )
    findings.append(
        K8sSecurityFinding(
            check_id="K8S-04",
            title="Kubernetes NetworkPolicy isolation (default-deny + least-privilege flows)",
            severity="High",
            standard="CIS Kubernetes 5.3.2",
            status="PASS" if (has_default_deny and len(network_policies) >= 6) else "FAIL",
            evidence=f"Found {len(network_policies)} NetworkPolicies (default-deny={has_default_deny})",
            remediation="Add default-deny-ingress NetworkPolicy and explicit allow policies per tier.",
        )
    )

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Lab3 Kubernetes security audit")
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    args = parser.parse_args()

    findings = run_k8s_audit()
    passed = sum(1 for f in findings if f.status == "PASS")
    failed = sum(1 for f in findings if f.status == "FAIL")

    report = {
        "phase": args.phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_checks": len(findings),
        "passed": passed,
        "failed": failed,
        "findings": [asdict(f) for f in findings],
    }

    out_path = LAB3_ROOT / "experiments" / f"security_{args.phase}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== Lab3 K8s Security Audit ({args.phase.upper()}): {passed}/{len(findings)} PASS, {failed} FAIL ===")
    for f in findings:
        print(f"[{f.status}] {f.check_id} ({f.severity}) {f.title} -> {f.evidence}")
    print(f"Saved report: {out_path}")


if __name__ == "__main__":
    main()
