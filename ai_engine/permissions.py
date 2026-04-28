from rest_framework import permissions


class IsAIModelManager(permissions.BasePermission):
    allowed_roles = {'general_manager', 'service_team_lead'}

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return getattr(user, 'role', None) in self.allowed_roles
