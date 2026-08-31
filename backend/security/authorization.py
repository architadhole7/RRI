class AccessDeniedError(Exception):
    pass


class RoleAuthorization:
    """Enforces role-based access control (RBAC) across system operations."""

    ROLE_PERMISSIONS = {
        "admin": ["read", "write", "execute", "approve", "kill_switch"],
        "merchant_operator": ["read", "write", "execute", "approve"],
        "read_only": ["read"],
    }

    def check_permission(self, role: str, required_permission: str) -> None:
        perms = self.ROLE_PERMISSIONS.get(role, [])
        if required_permission not in perms:
            raise AccessDeniedError(
                f"Role '{role}' is not authorized to perform action requiring '{required_permission}' permission"
            )
