from rest_framework.permissions import BasePermission


class BaseRolePermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsSuperAdmin(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_super_admin


class IsHost(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_host


class IsEndUser(BaseRolePermission):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_user


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):

        if hasattr(obj, 'is_deleted') and obj.is_deleted:
            return False

        if hasattr(obj, 'host'):
            return obj.host == request.user or request.user.is_super_admin

        if hasattr(obj, 'user'):
            return obj.user == request.user or request.user.is_super_admin

        return False


class IsSameTenant(BasePermission):
    def has_object_permission(self, request, view, obj):

        if hasattr(obj, 'is_deleted') and obj.is_deleted:
            return False

        user_tenant = getattr(request.user, "tenant", None)
        obj_tenant = getattr(obj, "tenant", None)

        if not obj_tenant and hasattr(obj, "property"):
            obj_tenant = getattr(obj.property, "tenant", None)

        return bool(user_tenant and obj_tenant and user_tenant == obj_tenant)