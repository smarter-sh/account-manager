# pylint: disable=W0707,W0718
"""Account views for Account Manager API."""

import logging
from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from am.apps.account.models import Account
from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .base import AccountListViewBase, AccountViewBase


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class AccountView(AccountViewBase):
    """
    Account view for Account Manager API.

    A superuser may read, update, create and delete any Account. A staff user may
    read and update only the Account of their own UserProfile.
    """

    def get_account(self, account_id: int) -> Account:
        """
        The Account that the request user asked for, if they may see it.

        :param account_id: The Account's id.
        :returns: The Account.
        :raises Http404: when a superuser asks for an Account that does not exist.
        :raises PermissionDenied: when anyone else asks for an Account other than their own.
        """
        if self.is_request_superuser:
            return get_object_or_404(Account, pk=account_id)
        account = self.get_request_user_account()
        if account.id != account_id:  # type: ignore[attr-defined]
            raise PermissionDenied("You are not authorized to access this account.")
        return account

    def require_superuser(self):
        """
        Refuse the request unless its user is a superuser.

        :raises PermissionDenied: when the request user is not a superuser.
        """
        if not self.is_request_superuser:
            raise PermissionDenied("Only a superuser may create or delete accounts.")

    def get(self, request: Request, account_id: int):
        """
        Return an Account as json.

        :param request: The request.
        :param account_id: The Account's id.
        :returns: The serialized Account.
        """
        logger.info("%s.get() account_id: %s", self.formatted_class_name, account_id)
        account = self.get_account(account_id)
        return Response(self.serializer_class(account).data, status=HTTPStatus.OK)

    # pylint: disable=W0613
    def post(self, request: Request, account_id: int):
        """
        Create an Account from the json dict in the request body.

        Superusers only.

        :param request: The request, whose body holds the new Account's fields (snake_case).
        :param account_id: Unused; the url names an existing Account.
        :returns: The new Account with status 201, or a 400 response when the body is
            not a json dict or the Account cannot be created.
        """
        logger.info("%s.post()", self.formatted_class_name)
        self.require_superuser()
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"error": f"Invalid request data. Expected a JSON dict but received {type(data).__name__}"},
                status=HTTPStatus.BAD_REQUEST,
            )
        try:
            account = Account.objects.create(**data)
        except Exception as e:
            return Response({"error": "Invalid request data", "exception": str(e)}, status=HTTPStatus.BAD_REQUEST)
        logger.info("%s.post() created account %s", self.formatted_class_name, account.id)  # type: ignore[attr-defined]
        return Response(self.serializer_class(account).data, status=HTTPStatus.CREATED)

    def patch(self, request: Request, account_id: int):
        """
        Update an Account's fields from the json dict in the request body.

        Keys that are not attributes of the Account are ignored.

        :param request: The request, whose body holds the fields to change (snake_case).
        :param account_id: The Account's id.
        :returns: The updated Account, or a 400 response when the body or a value is invalid.
        """
        logger.info("%s.patch() account_id: %s", self.formatted_class_name, account_id)
        account = self.get_account(account_id)
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"error": f"Invalid request data. Expected a JSON dict but received {type(data).__name__}"},
                status=HTTPStatus.BAD_REQUEST,
            )
        try:
            for key, value in data.items():
                if key not in ("id", "pk") and hasattr(account, key):
                    setattr(account, key, value)
            account.full_clean()
            account.save()
        except ValidationError as e:
            return Response({"error": "Invalid request data", "exception": str(e)}, status=HTTPStatus.BAD_REQUEST)
        return Response(self.serializer_class(account).data, status=HTTPStatus.OK)

    def delete(self, request: Request, account_id: int):
        """
        Delete an Account, and with it its UserProfiles.

        Superusers only.

        :param request: The request.
        :param account_id: The Account's id.
        :returns: An empty 204 response.
        :raises Http404: when the Account does not exist.
        """
        logger.info("%s.delete() account_id: %s", self.formatted_class_name, account_id)
        self.require_superuser()
        account = get_object_or_404(Account, pk=account_id)
        account.delete()
        return Response(status=HTTPStatus.NO_CONTENT)


class AccountListView(AccountListViewBase):
    """Account list view for Account Manager API: every Account for a superuser, else the user's own."""

    def get_queryset(self) -> QuerySet[Account]:
        """
        The Accounts the request user may see.

        :returns: Every Account for a superuser, else the Accounts of the user's UserProfiles.
        """
        if self.is_request_superuser:
            return Account.objects.all().order_by("pk")
        return Account.objects.filter(users__user=self.request_user).order_by("pk")
