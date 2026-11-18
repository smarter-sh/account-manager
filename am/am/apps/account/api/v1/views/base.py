# pylint: disable=W0707,W0718
"""Base classes of the account views of the Account Manager API."""

from typing import Optional

from rest_framework.exceptions import PermissionDenied

from am.apps.account.models import Account, User, UserProfile, get_resolved_user
from am.apps.account.serializers import AccountSerializer
from am.lib.drf.views.token_authentication_helpers import (
    AMAdminAPIView,
    AMAdminListAPIView,
)


class AccountViewMixin:
    """
    Helpers that the account views share to decide what the request user may see.

    A superuser may see every Account. A staff user may see only the Account of
    their own UserProfile.
    """

    request: object

    @property
    def request_user(self) -> Optional[User]:
        """
        The request's user, resolved to a :class:`User`.

        :returns: The user, or None for an anonymous request.
        """
        user = get_resolved_user(self.request.user)  # type: ignore[attr-defined]
        return user if isinstance(user, User) else None

    @property
    def is_request_superuser(self) -> bool:
        """
        Whether the request's user is a superuser.

        :returns: True for a superuser.
        """
        user = self.request_user
        return bool(user and user.is_superuser)

    def get_request_user_account(self) -> Account:
        """
        The Account of the request user's UserProfile.

        :returns: The Account.
        :raises PermissionDenied: when the request user has no UserProfile.
        """
        user_profile = UserProfile.objects.filter(user=self.request_user).order_by("pk").first()
        if user_profile is None:
            raise PermissionDenied("You are not associated with any account.")
        return user_profile.account


class AccountViewBase(AccountViewMixin, AMAdminAPIView):
    """Base class for account views."""

    serializer_class = AccountSerializer


class AccountListViewBase(AccountViewMixin, AMAdminListAPIView):
    """Base class for account list views."""

    serializer_class = AccountSerializer
