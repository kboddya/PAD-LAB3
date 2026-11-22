"""Automated Kubernetes CIS & Pod Security Standards tests for Lab3."""

from __future__ import annotations

import sys
from pathlib import Path

LAB3_ROOT = Path(__file__).resolve().parent.parent
if str(LAB3_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB3_ROOT))

from scripts.k8s_security_audit import run_k8s_audit  # noqa: E402


def test_all_four_kubernetes_security_controls_pass() -> None:
    findings = run_k8s_audit()
    assert len(findings) == 4
    failures = [f"{f.check_id}: {f.evidence}" for f in findings if f.status != "PASS"]
    assert not failures, f"Kubernetes security audit failures detected: {failures}"
