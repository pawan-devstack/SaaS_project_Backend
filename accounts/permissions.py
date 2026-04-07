from rest_framework.permissions import BasePermission


# Base Permission
class BaseRolePermission(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


# Super Admin
class IsSuperAdmin(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_super_admin


# Host
class IsHost(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.user.is_host or request.user.is_super_admin
        )


# End User (STRICT)
class IsEndUser(BaseRolePermission):from rest_framework.permissions import BasePermission


# =========================
# Base Permission
# =========================
class BaseRolePermission(BasePermission):
    """
    Ensures user is authenticated
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


# =========================
# Super Admin (Full Access)
# =========================
class IsSuperAdmin(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_super_admin


# =========================
# Host (Admin Override)
# =========================
class IsHost(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (
            request.user.is_host or request.user.is_super_admin
        )


# =========================
# End User (Strict Access)
# =========================
class IsEndUser(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_user


# =========================
# Owner Permission (Object Level)
# =========================
class IsOwner(BasePermission):
    """
    Allows access only to object owner
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


# =========================
# Tenant Based Permission 
# =========================
class IsSameTenant(BasePermission):
    """
    Ensures user and object belong to same tenant
    """
    def has_object_permission(self, request, view, obj):
        user_tenant = getattr(request.user, "tenant", None)
        obj_tenant = getattr(obj, "tenant", None)

        return user_tenant and obj_tenant and user_tenant == obj_tenant
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_user