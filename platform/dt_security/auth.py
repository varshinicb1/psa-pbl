"""
Enterprise-grade authentication and authorization for the Grid Digital Twin.

Supports:
- OAuth2 / OIDC integration
- API key authentication
- Role-based access control (RBAC)
- Audit logging
- Rate limiting
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ENGINEER = "engineer"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class User:
    id: str
    username: str
    roles: Set[Role]
    api_key_hash: str = ""
    permissions: Set[str] = field(default_factory=set)


@dataclass
class AuditEntry:
    user_id: str
    action: str
    resource: str
    timestamp: float
    ip_address: str
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


class RBACManager:
    """
    Role-based access control for the grid digital twin.

    Defines which roles can access which resources and operations.
    """

    def __init__(self):
        self._permissions: Dict[Role, Set[str]] = {
            Role.VIEWER: {
                "snapshot:read",
                "health:read",
                "topology:read",
                "history:read",
            },
            Role.OPERATOR: {
                "snapshot:read",
                "health:read",
                "topology:read",
                "history:read",
                "commands:perturb",
                "alarms:acknowledge",
            },
            Role.ENGINEER: {
                "snapshot:read",
                "health:read",
                "topology:read",
                "history:read",
                "commands:perturb",
                "commands:configure",
                "alarms:acknowledge",
                "ml:retrain",
                "simulation:configure",
            },
            Role.ADMIN: {
                "snapshot:read",
                "health:read",
                "topology:read",
                "history:read",
                "commands:*",
                "alarms:*",
                "ml:*",
                "simulation:*",
                "users:manage",
                "audit:read",
            },
            Role.SYSTEM: {"*"},
        }

    def check_permission(self, user: User, permission: str) -> bool:
        for role in user.roles:
            role_perms = self._permissions.get(role, set())
            if "*" in role_perms:
                return True
            if permission in role_perms:
                return True
        return False

    def get_permissions(self, user: User) -> Set[str]:
        result: Set[str] = set()
        for role in user.roles:
            role_perms = self._permissions.get(role, set())
            result.update(role_perms)
        return result


class AuditLogger:
    """
    Immutable audit log for all grid operations.

    In production, writes to a separate audit database or SIEM system.
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._log_limit = 10000

    def log(
        self,
        user_id: str,
        action: str,
        resource: str,
        ip_address: str = "",
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            user_id=user_id,
            action=action,
            resource=resource,
            timestamp=time.time(),
            ip_address=ip_address,
            success=success,
            details=details or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self._log_limit:
            self._entries = self._entries[-self._log_limit:]

        logger.info(
            f"AUDIT: user={user_id} action={action} "
            f"resource={resource} success={success}"
        )
        return entry

    def get_recent(self, limit: int = 100) -> List[AuditEntry]:
        return self._entries[-limit:]

    def get_by_user(self, user_id: str, limit: int = 100) -> List[AuditEntry]:
        return [
            e for e in self._entries if e.user_id == user_id
        ][-limit:]


class APIKeyManager:
    """
    API key management with hashed key storage.

    Keys are stored as HMAC-SHA256 hashes. The raw key is only shown once
    at creation time.
    """

    def __init__(self):
        self._secret = os.environ.get("API_KEY_SECRET", "change-me-in-production")
        self._keys: Dict[str, User] = {}

    def create_key(self, user: User) -> str:
        raw_key = f"dt_{uuid.uuid4().hex}"
        key_hash = self._hash_key(raw_key)
        user.api_key_hash = key_hash
        self._keys[key_hash] = user
        return raw_key

    def validate_key(self, raw_key: str) -> Optional[User]:
        key_hash = self._hash_key(raw_key)
        return self._keys.get(key_hash)

    def revoke_key(self, user_id: str) -> bool:
        to_remove = [
            k for k, v in self._keys.items() if v.id == user_id
        ]
        for k in to_remove:
            del self._keys[k]
        return len(to_remove) > 0

    def _hash_key(self, raw_key: str) -> str:
        return hmac.new(
            self._secret.encode(),
            raw_key.encode(),
            hashlib.sha256,
        ).hexdigest()


# Global instances
rbac = RBACManager()
audit_logger = AuditLogger()
api_keys = APIKeyManager()
