"""Test the subscription status api (``am.apps.account.api.v1.views.subscription_status``)."""

from datetime import date, timedelta
from http import HTTPStatus
from typing import Optional

from django.test import Client
from django.urls import reverse
from waffle.testutils import override_switch

from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.models import (
    Account,
    PlatformClient,
    Subscription,
    SubscriptionUser,
    User,
    UserProfile,
)
from am.lib.django.waffle import AMWaffleSwitches

from .mixins import AccountTestCase

PLATFORM_HOST = "alpha.platform.example.com"


class TestSubscriptionStatusView(AccountTestCase):
    """
    Test SubscriptionStatusView: who may ask, and who is answered 200.

    ``user`` belongs to an active, current MULTITENANT subscription; ``platform`` is a registered
    platform, and ``key`` its key.
    """

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Subscription Status Co")
        cls.user = User.objects.create_user(username="subscriber", email="Subscriber@Example.com")
        cls.subscription = cls.make_subscription(cls.account, cls.user)
        cls.platform, cls.key = PlatformClient.create_with_key(PLATFORM_HOST)

    @staticmethod
    def make_subscription(account, user=None, **kwargs) -> Subscription:
        """
        Create a subscription, active and current unless kwargs say otherwise, with user as its member.

        :param account: The subscription's account.
        :param user: The user to add as a SubscriptionUser, or None.
        :returns: The subscription.
        """
        values = {
            "plan_type": AMHostingPlanTypeEnum.MULTITENANT.value,
            "start_date": date.today() - timedelta(days=1),
            "end_date": date.today() + timedelta(days=30),
            "comment": "internal note",
        }
        values.update(kwargs)
        subscription = Subscription.objects.create(account=account, **values)
        if user is not None:
            SubscriptionUser.objects.create(subscription=subscription, user=user)
        return subscription

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.path = reverse("api:v1:account:subscription_status_view")

    def ask(
        self,
        username: Optional[str] = "subscriber",
        email: Optional[str] = "subscriber@example.com",
        key: Optional[str] = None,
        method: str = "get",
        **headers,
    ):
        """
        Ask the api about a user.

        :param username: The X-Client-Username header, or None to leave it out.
        :param email: The X-Client-Email header, or None to leave it out.
        :param key: The platform key, or None to send none.
        :param method: The http method.
        :param headers: More headers, e.g. HTTP_X_API_KEY.
        :returns: The response.
        """
        if username is not None:
            headers["HTTP_X_CLIENT_USERNAME"] = username
        if email is not None:
            headers["HTTP_X_CLIENT_EMAIL"] = email
        if key is not None:
            headers["HTTP_AUTHORIZATION"] = f"Platform {key}"
        return getattr(self.client, method)(self.path, **headers)

    # -------------------------------------------------------------------------
    # with a platform key
    # -------------------------------------------------------------------------
    def test_active_subscriber_is_answered_200_with_a_minimal_body(self):
        """The answer says active, the plan and the end date, and nothing about the account."""
        response = self.ask(key=self.key)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            response.json(),
            {"active": True, "plan_type": "multitenant", "end_date": self.subscription.end_date.isoformat()},
        )

    def test_email_matches_in_any_case(self):
        """The email address is compared without regard to case."""
        self.assertEqual(self.ask(email="SUBSCRIBER@EXAMPLE.COM", key=self.key).status_code, HTTPStatus.OK)

    def test_same_username_with_another_email_is_refused(self):
        """A different person with the same username on the platform is not the subscriber."""
        self.assertEqual(self.ask(email="someone.else@example.com", key=self.key).status_code, HTTPStatus.FORBIDDEN)

    def test_email_is_required_with_a_key(self):
        """A platform with a key must say who the user is by email too."""
        self.assertEqual(self.ask(email=None, key=self.key).status_code, HTTPStatus.BAD_REQUEST)

    def test_username_is_required(self):
        """Without a username there is nobody to answer about."""
        self.assertEqual(self.ask(username=None, key=self.key).status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(self.ask(username="   ", key=self.key).status_code, HTTPStatus.BAD_REQUEST)

    def test_unknown_user_and_unsubscribed_user_are_answered_alike(self):
        """403 for both, so the api doesn't reveal which usernames exist."""
        User.objects.create_user(username="unsubscribed", email="unsubscribed@example.com")
        unknown = self.ask(username="nobody", email="nobody@example.com", key=self.key)
        unsubscribed = self.ask(username="unsubscribed", email="unsubscribed@example.com", key=self.key)
        self.assertEqual(unknown.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(unsubscribed.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(unknown.content, unsubscribed.content)

    def test_only_a_multitenant_subscription_counts(self):
        """A hosted or managed platform subscription doesn't admit its users to the multitenant platform."""
        user = User.objects.create_user(username="hosted_user", email="hosted@example.com")
        for plan_type in (AMHostingPlanTypeEnum.HOSTED_PLATFORM, AMHostingPlanTypeEnum.MANAGED_PLATFORM):
            self.make_subscription(self.account, user, plan_type=plan_type.value)
        self.assertEqual(
            self.ask(username="hosted_user", email="hosted@example.com", key=self.key).status_code,
            HTTPStatus.FORBIDDEN,
        )

    def test_inactive_expired_and_future_subscriptions_dont_count(self):
        """Only an active subscription whose dates include today admits the user."""
        cases = {
            "inactive_user": {"active": False},
            "expired_user": {"end_date": date.today()},
            "future_user": {"start_date": date.today() + timedelta(days=1)},
        }
        for username, kwargs in cases.items():
            with self.subTest(username):
                user = User.objects.create_user(username=username, email=f"{username}@example.com")
                self.make_subscription(self.account, user, **kwargs)
                response = self.ask(username=username, email=f"{username}@example.com", key=self.key)
                self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_account_subscription_without_the_user_doesnt_count(self):
        """A user is admitted by a subscription they belong to, not by their account's."""
        user = User.objects.create_user(username="account_member", email="member@example.com")
        UserProfile.objects.create(user=user, account=self.account, is_test=True)
        self.assertEqual(
            self.ask(username="account_member", email="member@example.com", key=self.key).status_code,
            HTTPStatus.FORBIDDEN,
        )

    def test_deactivated_user_is_refused(self):
        """A user whose Django account is inactive is refused, whatever their subscription."""
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.ask(key=self.key).status_code, HTTPStatus.FORBIDDEN)

    def test_wrong_key_is_refused(self):
        """A key that belongs to no platform is answered 401."""
        response = self.ask(key="not-a-real-platform-key")
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Platform")

    def test_inactive_platform_is_refused(self):
        """A deactivated platform's key no longer works."""
        PlatformClient.objects.filter(pk=self.platform.pk).update(is_active=False)
        self.assertEqual(self.ask(key=self.key).status_code, HTTPStatus.UNAUTHORIZED)

    def test_malformed_platform_header_is_refused(self):
        """The Platform scheme without a key, or with two, is answered 401."""
        for value in ("Platform", f"Platform {self.key} extra"):
            with self.subTest(value):
                response = self.client.get(self.path, HTTP_AUTHORIZATION=value, HTTP_X_CLIENT_USERNAME="subscriber")
                self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_rotated_key_replaces_the_old_one(self):
        """After a rotation, only the new key works."""
        new_key = self.platform.rotate_key()
        self.assertEqual(self.ask(key=self.key).status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(self.ask(key=new_key).status_code, HTTPStatus.OK)

    def test_other_methods_are_answered_as_get(self):
        """POST, PUT and PATCH are answered as GET is, for older callers."""
        for method in ("post", "put", "patch"):
            with self.subTest(method):
                self.assertEqual(self.ask(key=self.key, method=method).status_code, HTTPStatus.OK)

    # -------------------------------------------------------------------------
    # without a platform key
    # -------------------------------------------------------------------------
    def test_without_a_key_the_username_alone_is_answered_until_keys_are_required(self):
        """Platforms not yet given a key keep working while the require_platform_key switch is off."""
        self.assertEqual(self.ask(email=None).status_code, HTTPStatus.OK)
        self.assertEqual(self.ask(username="nobody", email=None).status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(self.ask(username=None, email=None).status_code, HTTPStatus.BAD_REQUEST)

    @override_switch(AMWaffleSwitches.REQUIRE_PLATFORM_KEY, active=True)
    def test_without_a_key_is_refused_once_keys_are_required(self):
        """With the switch on, only a platform with a key is answered."""
        response = self.ask(email=None)
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Platform")
        self.assertEqual(self.ask(key=self.key).status_code, HTTPStatus.OK)

    def test_an_account_number_in_x_api_key_authenticates_nobody(self):
        """
        X-API-KEY with an account number once signed the caller in as the account's admin.

        It is ignored now, and the request doesn't create an admin user for the account.
        """
        users_before = User.objects.count()
        response = self.ask(username="nobody", email=None, HTTP_X_API_KEY=self.account.account_number)
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(User.objects.count(), users_before)
