"""Tests for government compliance modules."""

from __future__ import annotations

import pathlib
import sys

# Bootstrap paths for local development
_repo_root = pathlib.Path(__file__).resolve().parents[3]
for _mod in ["dt-compliance/src", "dt-contracts/python/src", "dt-orchestrator"]:
    _p = str(_repo_root / "platform" / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from dt_compliance.nerc_cip import NERCCIPChecker, CIPStatus
from dt_compliance.indian_grid_code import IndianGridCodeChecker, ComplianceStatus
from dt_compliance.encryption import EncryptionManager, RetentionClass


class TestNERCCIP:
    def setup_method(self):
        self.checker = NERCCIPChecker()

    def test_full_audit_compliant(self):
        ctx = {
            "has_authentication": True,
            "has_rbac": True,
            "has_audit_logging": True,
            "has_encryption_at_rest": True,
            "has_tls": True,
            "has_disaster_recovery": True,
            "has_business_continuity": True,
            "has_incident_response_plan": True,
            "has_configuration_baseline": True,
            "has_change_management": True,
        }
        report = self.checker.audit(ctx)
        assert report.total_count == 10
        assert report.score > 0

    def test_non_compliant_detected(self):
        ctx = {"has_authentication": False, "has_rbac": False}
        report = self.checker.audit(ctx)
        assert any(r.status == CIPStatus.NON_COMPLIANT for r in report.requirements)


class TestIndianGridCode:
    def setup_method(self):
        self.checker = IndianGridCodeChecker()

    def test_audit_produces_report(self):
        report = self.checker.audit(None)
        assert report.grid_region == "South"
        assert report.state == "Karnataka"
        assert report.utility == "BESCOM"
        assert len(report.checks) >= 5

    def test_voltage_check_with_snapshot(self):
        from dt_contracts.models import GridGraphSnapshot, GridNode
        nodes = [GridNode(
            id="bus_1", type="Bus",
            static={"vn_kv": 220.0},
            dynamic={"vm_pu": 1.02},
        )]
        snap = GridGraphSnapshot(t="2026-01-01T00:00:00Z", topology_hash="h1", nodes=nodes)
        report = self.checker.audit(snap)
        assert report.score >= 0


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        em = EncryptionManager()
        original = {"bus_id": "bus_1", "voltage": 1.02, "timestamp": "2026-01-01T00:00:00Z"}
        encrypted = em.encrypt_value(original)
        assert encrypted != str(original)
        decrypted = em.decrypt_value(encrypted)
        assert decrypted == original

    def test_retention_policies(self):
        em = EncryptionManager()
        rt = em.get_retention_policy(RetentionClass.REAL_TIME)
        assert rt.retention_days == 7
        comp = em.get_retention_policy(RetentionClass.COMPLIANCE)
        assert comp.retention_days == 1825
        assert comp.auto_purge is False

    def test_key_rotation(self):
        em = EncryptionManager()
        original = "test_data"
        encrypted = em.encrypt_value(original)
        em.rotate_key()
        decrypted = em.decrypt_value(encrypted)
        assert decrypted == original
