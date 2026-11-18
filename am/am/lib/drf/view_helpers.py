"""Django template and view helper functions."""

from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


# ------------------------------------------------------------------------------
# API public views
# ------------------------------------------------------------------------------
class UnauthenticatedPermissionClass(BasePermission):
    """Allows public access to APIS."""

    def has_permission(self, request: Request, view) -> bool:
        return True


class AMUnauthenticatedAPIView(APIView):
    """Base API view for Account Manager."""

    permission_classes = [UnauthenticatedPermissionClass]


class AMUnauthenticatedAPIListView(ListAPIView):
    """Base API listview for Account Manager."""

    permission_classes = [UnauthenticatedPermissionClass]
