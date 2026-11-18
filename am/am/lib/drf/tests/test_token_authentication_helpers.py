"""Test the base DRF views in am.lib.drf.views.token_authentication_helpers."""

from http import HTTPStatus
from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from am.apps.account.tests.mixins import TestAccountMixin
from am.apps.account.utils import get_cached_account_for_user, get_cached_user_profile
from am.apps.api.signals import api_request_completed, api_request_initiated
from am.lib.drf.views.token_authentication_helpers import (
    AMAdminAPIView,
    AMAdminListAPIView,
    AMAuthenticatedAPIView,
    AMAuthenticatedListAPIView,
)


class AuthenticatedView(AMAuthenticatedAPIView):
    """An authenticated detail view."""

    def get(self, request, *args, **kwargs):
        assert self.account is not None
        return Response({"user": request.user.get_username(), "account": self.account.account_number})


class AuthenticatedListView(AMAuthenticatedListAPIView):
    """An authenticated list view."""

    def get(self, request, *args, **kwargs):
        return Response([request.user.get_username()])


class AdminView(AMAdminAPIView):
    """An admin detail view."""

    def get(self, request, *args, **kwargs):
        return Response({"user": request.user.get_username()})


class AdminListView(AMAdminListAPIView):
    """An admin list view."""

    def get(self, request, *args, **kwargs):
        return Response([request.user.get_username()])


class TestTokenAuthenticationHelpers(TestAccountMixin):
    """Test the authenticated and admin base views."""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        # the cached lookups are keyed by row id, which an earlier run of the same test database
        # may have cached for other rows: start from fresh ones.
        for user in (self.admin_user, self.non_admin_user):
            get_cached_account_for_user(user, invalidate=True)
            get_cached_user_profile(user, invalidate=True)
            get_cached_user_profile(user, account=self.account, invalidate=True)

    def receive(self, signal):
        """Connect a mock receiver to a signal for the duration of the test."""
        receiver = MagicMock()
        signal.connect(receiver)
        self.addCleanup(signal.disconnect, receiver)
        return receiver

    def get(self, view_class, user):
        request = self.factory.get("/api/v1/tests/")
        request.user = user
        return view_class.as_view()(request)

    def test_authenticated_views_answer_a_user(self):
        on_initiated = self.receive(api_request_initiated)
        response = self.get(AuthenticatedView, self.non_admin_user)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, {"user": self.non_admin_user.username, "account": self.account.account_number})
        on_initiated.assert_called_once()
        response = self.get(AuthenticatedListView, self.non_admin_user)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.data, [self.non_admin_user.username])

    def test_authenticated_views_redirect_anonymous_to_login(self):
        for view_class in (AuthenticatedView, AuthenticatedListView):
            with self.subTest(view=view_class.__name__):
                response = self.get(view_class, AnonymousUser())
                self.assertEqual(response.status_code, HTTPStatus.FOUND)
                self.assertIn("login", response["Location"])

    def test_admin_views_answer_staff(self):
        on_initiated = self.receive(api_request_initiated)
        on_completed = self.receive(api_request_completed)
        for view_class in (AdminView, AdminListView):
            with self.subTest(view=view_class.__name__):
                response = self.get(view_class, self.admin_user)
                self.assertEqual(response.status_code, HTTPStatus.OK)
                self.assertIn(self.admin_user.username, str(response.data))
        self.assertEqual(on_initiated.call_count, 2)
        self.assertEqual(on_completed.call_count, 2)

    def test_admin_views_redirect_anonymous_and_non_staff(self):
        for view_class in (AdminView, AdminListView):
            for user in (AnonymousUser(), self.non_admin_user):
                with self.subTest(view=view_class.__name__, user=str(user)):
                    response = self.get(view_class, user)
                    self.assertEqual(response.status_code, HTTPStatus.FOUND)
                    self.assertIn("login", response["Location"])
