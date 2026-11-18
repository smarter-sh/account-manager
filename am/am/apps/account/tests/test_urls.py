"""Test the url conf of the account api (``am.apps.account.api.v1.urls``)."""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from am.apps.account.api.v1.views.account import AccountListView, AccountView
from am.apps.account.api.v1.views.payment_methods import (
    PaymentMethodsListView,
    PaymentMethodView,
)
from am.apps.account.api.v1.views.subscription_status import SubscriptionStatusView
from am.apps.account.api.v1.views.user import UserListView, UserView


class TestUrls(SimpleTestCase):
    """Every account api url name reverses to its path, which resolves to its view."""

    namespace = "api:v1:account:"

    def assert_route(self, name: str, args: list, path: str, view_class):
        """
        Assert that ``name`` reverses to ``path``, and that ``path`` resolves to ``view_class``.

        :param name: The url name, without the namespace.
        :param args: The url's arguments.
        :param path: The expected path.
        :param view_class: The expected view class.
        """
        self.assertEqual(reverse(self.namespace + name, args=args), path)
        self.assertIs(resolve(path).func.view_class, view_class)  # type: ignore[attr-defined]

    def test_routes(self):
        """Test each route of the account api."""
        prefix = "/api/v1/accounts/"
        self.assert_route("account_list_view", [], prefix, AccountListView)
        self.assert_route("subscription_status_view", [], prefix + "subscription-status/", SubscriptionStatusView)
        self.assert_route("account_view", [7], prefix + "7/", AccountView)
        self.assert_route("account_users_list_view", [], prefix + "users/", UserListView)
        self.assert_route("account_user_view", [7], prefix + "users/7/", UserView)
        self.assert_route("account_payment_methods_list_view", [], prefix + "payment-methods/", PaymentMethodsListView)
        self.assert_route("account_payment_method_view", [7], prefix + "payment-methods/7/", PaymentMethodView)
