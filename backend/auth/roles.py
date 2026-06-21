"""Application roles and permission helpers."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    FLEET_MANAGER = "fleet_manager"
    INSPECTOR = "inspector"
    VIEWER = "viewer"


ROLE_RANK: dict[str, int] = {
    UserRole.VIEWER: 1,
    UserRole.INSPECTOR: 2,
    UserRole.FLEET_MANAGER: 3,
    UserRole.ADMIN: 4,
}


def role_at_least(role: str, minimum: UserRole) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK[minimum]


def can_capture(role: str) -> bool:
    return role_at_least(role, UserRole.INSPECTOR)


def can_manage_fleet(role: str) -> bool:
    return role_at_least(role, UserRole.FLEET_MANAGER)


def can_admin(role: str) -> bool:
    return role == UserRole.ADMIN
