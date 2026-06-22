"""Tests for security and authentication."""
from __future__ import annotations

import pytest
from dt_security.auth import (
    RBACManager, AuditLogger, APIKeyManager,
    Role, User,
)


class TestRBAC:
    def setup_method(self):
        self.rbac = RBACManager()

    def test_viewer_permissions(self):
        user = User(id="1", username="viewer", roles={Role.VIEWER})
        assert self.rbac.check_permission(user, "snapshot:read") is True
        assert self.rbac.check_permission(user, "commands:perturb") is False

    def test_operator_permissions(self):
        user = User(id="2", username="operator", roles={Role.OPERATOR})
        assert self.rbac.check_permission(user, "snapshot:read")
        assert self.rbac.check_permission(user, "commands:perturb")
        assert self.rbac.check_permission(user, "users:manage") is False

    def test_admin_permissions(self):
        user = User(id="3", username="admin", roles={Role.ADMIN})
        assert self.rbac.check_permission(user, "snapshot:read")
        assert self.rbac.check_permission(user, "users:manage")
        assert self.rbac.check_permission(user, "commands:*")

    def test_system_wildcard(self):
        user = User(id="4", username="system", roles={Role.SYSTEM})
        assert self.rbac.check_permission(user, "anything:at:all")


class TestAuditLogger:
    def setup_method(self):
        self.audit = AuditLogger()

    def test_log_entry(self):
        entry = self.audit.log(
            user_id="user_1",
            action="snapshot:read",
            resource="/snapshot",
            ip_address="192.168.1.1",
        )
        assert entry.user_id == "user_1"
        assert entry.action == "snapshot:read"
        assert entry.success is True

    def test_recent_entries(self):
        self.audit.log("user_1", "read", "/health")
        self.audit.log("user_1", "read", "/snapshot")
        recent = self.audit.get_recent(limit=1)
        assert len(recent) == 1

    def test_get_by_user(self):
        self.audit.log("user_a", "action_1", "/resource_1")
        self.audit.log("user_b", "action_2", "/resource_2")
        user_a_entries = self.audit.get_by_user("user_a")
        assert len(user_a_entries) == 1


class TestAPIKeyManager:
    def setup_method(self):
        self.key_mgr = APIKeyManager()

    def test_create_and_validate(self):
        user = User(id="u1", username="test_user", roles={Role.VIEWER})
        raw_key = self.key_mgr.create_key(user)
        assert raw_key.startswith("dt_")
        validated = self.key_mgr.validate_key(raw_key)
        assert validated is not None
        assert validated.id == "u1"

    def test_invalid_key(self):
        validated = self.key_mgr.validate_key("invalid_key")
        assert validated is None

    def test_revoke(self):
        user = User(id="u2", username="revoke_user", roles={Role.VIEWER})
        self.key_mgr.create_key(user)
        assert self.key_mgr.revoke_key("u2") is True
        assert self.key_mgr.revoke_key("nonexistent") is False
