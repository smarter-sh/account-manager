# pylint: disable=W0707,W0718,W0613
"""User views for Account Manager API."""

import logging
from http import HTTPStatus

from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from am.apps.account.models import User, UserProfile
from am.apps.account.serializers import UserSerializer
from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .base import AccountListViewBase, AccountViewBase


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.API_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)

#: The fields of a new user that the request body may set.
USER_CREATE_FIELDS = ("username", "password", "email", "first_name", "last_name")
#: The fields of a user that the request body may update.
USER_UPDATE_FIELDS = ("username", "email", "first_name", "last_name", "is_active")


def invalid_body_response(data) -> Response:
    """
    The 400 response for a request body that is not a json dict.

    :param data: The parsed request body.
    :returns: The response.
    """
    return Response(
        {"error": f"Invalid request data. Expected a JSON dict but received {type(data).__name__}"},
        status=HTTPStatus.BAD_REQUEST,
    )


class UserView(AccountViewBase):
    """
    User view for Account Manager API.

    A superuser may read, update and delete any user. A staff user may do so only
    for the users of their own Account.
    """

    serializer_class = UserSerializer

    def get_user(self, user_id: int) -> User:
        """
        The User that the request user asked for, if they may see it.

        :param user_id: The User's id.
        :returns: The User.
        :raises Http404: when the User does not exist, or is not in the request user's Account.
        """
        if self.is_request_superuser:
            try:
                return User.objects.get(pk=user_id)
            except User.DoesNotExist:
                raise Http404("User not found")
        account = self.get_request_user_account()
        user_profile = UserProfile.objects.filter(account=account, user_id=user_id).select_related("user").first()
        if user_profile is None:
            raise Http404("User not found")
        return user_profile.user

    def get(self, request: Request, user_id: int):
        """
        Return a user as json.

        :param request: The request.
        :param user_id: The User's id.
        :returns: The serialized User.
        """
        logger.info("%s.get() user_id: %s", self.formatted_class_name, user_id)
        return Response(UserSerializer(self.get_user(user_id)).data, status=HTTPStatus.OK)

    def patch(self, request: Request, user_id: int):
        """
        Update a user's fields from the json dict in the request body.

        Only the fields in ``USER_UPDATE_FIELDS`` change; the others are ignored.

        :param request: The request, whose body holds the fields to change.
        :param user_id: The User's id.
        :returns: The updated User, or a 400 response when the body is not a json dict.
        """
        logger.info("%s.patch() user_id: %s", self.formatted_class_name, user_id)
        user = self.get_user(user_id)
        data = request.data
        if not isinstance(data, dict):
            return invalid_body_response(data)
        for key, value in data.items():
            if key in USER_UPDATE_FIELDS:
                setattr(user, key, value)
        user.save()
        return Response(UserSerializer(user).data, status=HTTPStatus.OK)

    def delete(self, request: Request, user_id: int):
        """
        Delete a user and its UserProfiles.

        :param request: The request.
        :param user_id: The User's id.
        :returns: An empty 204 response.
        :raises PermissionDenied: when the request user tries to delete themself.
        """
        logger.info("%s.delete() user_id: %s", self.formatted_class_name, user_id)
        user = self.get_user(user_id)
        if user == self.request_user:
            raise PermissionDenied("You cannot delete yourself.")
        with transaction.atomic():
            UserProfile.objects.filter(user=user).delete()
            user.delete()
        return Response(status=HTTPStatus.NO_CONTENT)

    def handle_exception(self, exc):
        """
        Answer an Http404 with a json 404 response, and leave any other exception to DRF.

        :param exc: The exception that the view raised.
        :returns: The response.
        """
        if isinstance(exc, Http404):
            return Response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        return super().handle_exception(exc)


class UserListView(AccountListViewBase):
    """User list view for Account Manager API: lists users, and creates one with POST."""

    serializer_class = UserSerializer

    def get_queryset(self) -> QuerySet[User]:
        """
        The users the request user may see.

        :returns: Every User for a superuser, else the Users of the request user's Accounts.
        """
        if self.is_request_superuser:
            return User.objects.all().order_by("pk")
        accounts = UserProfile.objects.filter(user=self.request_user).values("account")
        user_ids = UserProfile.objects.filter(account__in=accounts).values("user")
        return User.objects.filter(id__in=user_ids).order_by("pk")

    def post(self, request: Request, *args, **kwargs):
        """
        Create a user in the request user's Account from the json dict in the request body.

        The body needs a ``username`` and a ``password``; only the fields in
        ``USER_CREATE_FIELDS`` are used.

        :param request: The request.
        :returns: The new User with status 201, or a 400 response when the body is invalid.
        :raises PermissionDenied: when the request user has no UserProfile.
        """
        logger.info("%s.post()", self.formatted_class_name)
        data = request.data
        if not isinstance(data, dict):
            return invalid_body_response(data)
        missing = [field for field in ("username", "password") if not data.get(field)]
        if missing:
            return Response(
                {"error": f"Invalid request data. Missing field(s): {', '.join(missing)}"},
                status=HTTPStatus.BAD_REQUEST,
            )
        account = self.get_request_user_account()
        fields = {key: value for key, value in data.items() if key in USER_CREATE_FIELDS}
        try:
            with transaction.atomic():
                user = User.objects.create_user(**fields)
                UserProfile.objects.create(user=user, account=account)
        except Exception as e:
            return Response({"error": "Invalid request data", "exception": str(e)}, status=HTTPStatus.BAD_REQUEST)
        logger.info("%s.post() created user %s", self.formatted_class_name, user.id)  # type: ignore[attr-defined]
        return Response(UserSerializer(user).data, status=HTTPStatus.CREATED)
