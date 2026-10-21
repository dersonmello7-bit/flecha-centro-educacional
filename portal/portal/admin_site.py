from django.contrib.admin import AdminSite
from .access import can_administer_portal


class PortalAdminSite(AdminSite):
    def has_permission(self, request):
        return can_administer_portal(request.user)
