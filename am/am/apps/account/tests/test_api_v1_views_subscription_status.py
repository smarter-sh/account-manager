"""Test the subscription status view of the Account Manager API (``am.apps.account.api.v1.views.subscription_status``)."""

from datetime import date, timedelta
from http import HTTPStatus

from django.test import Client
from django.urls import reverse

from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.models import Subscription, SubscriptionUser

from .factories import factory_account_teardown, mortal_user_factory
from .mixins import TestAccountMixin


class TestApiV1ViewsSubscriptionStatus(TestAccountMixin):
    """
    Test SubscriptionStatusView.

    ``subscribed_user`` has an active Subscription; ``non_admin_user`` has none.
    """

    @classmethod
    def setUpClass(cls):
        """Create a user with an active Subscription."""
        super().setUpClass()
        cls.subscribed_user, cls.subscribed_account, cls.subscribed_user_profile = mortal_user_factory()
        cls.subscription = Subscription.objects.create(
            account=cls.subscribed_account,
            plan_type=AMHostingPlanTypeEnum.MULTITENANT.value,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            comment="unit test",
        )
        SubscriptionUser.objects.create(subscription=cls.subscription, user=cls.subscribed_user)

    @classmethod
    def tearDownClass(cls):
        """Delete the Subscription and its user."""
        cls.subscription.delete()
        factory_account_teardown(
            user=cls.subscribed_user, account=cls.subscribed_account, user_profile=cls.subscribed_user_profile
        )
        super().tearDownClass()

    def setUp(self):
        """An anonymous client: the view allows any caller."""
        super().setUp()
        self.client = Client()
        self.path = reverse("api:v1:account:subscription_status_view")

    def assert_subscription(self, response):
        """
        Assert that the response is a 200 with the test Subscription.

        :param response: The response.
        """
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["id"], self.subscription.pk)
        self.assertEqual(response.json()["account"], self.subscribed_account.pk)
        self.assertTrue(response.json()["active"])
        self.assertEqual(response.json()["planType"], AMHostingPlanTypeEnum.MULTITENANT.value)

    def test_get_username_in_query_params(self):
        """GET with ``username`` and ``requester`` query parameters finds the Subscription."""
        response = self.client.get(
            self.path, {"username": self.subscribed_user.username, "requester": "platform.example.com"}
        )
        self.assert_subscription(response)

    def test_get_username_in_headers(self):
        """GET with the X-Client-Username and X-Client-Domain headers finds the Subscription."""
        response = self.client.get(
            self.path,
            headers={"X-Client-Username": self.subscribed_user.username, "X-Client-Domain": "platform.example.com"},
        )
        self.assert_subscription(response)

    def test_post_username_in_body(self):
        """POST with a json body finds the Subscription."""
        response = self.client.post(
            self.path,
            {"username": self.subscribed_user.username, "requester": "platform.example.com"},
            content_type="application/json",
        )
        self.assert_subscription(response)

    def test_put_and_patch(self):
        """PUT and PATCH answer as GET does."""
        body = {"username": self.subscribed_user.username}
        self.assert_subscription(self.client.put(self.path, body, content_type="application/json"))
        self.assert_subscription(self.client.patch(self.path, body, content_type="application/json"))

    def test_no_username_is_not_found(self):
        """A request without a username is a 404."""
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unknown_username_is_not_found(self):
        """A username that does not exist is a 404."""
        response = self.client.get(self.path, {"username": f"no_such_user_{self.hash_suffix}"})
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_user_without_subscription_is_forbidden(self):
        """A user without an active Subscription is a 403."""
        response = self.client.get(self.path, {"username": self.non_admin_user.username})
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
