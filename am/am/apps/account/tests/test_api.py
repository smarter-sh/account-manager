# pylint: disable=wrong-import-position
"""
Test the account api end points, end to end, through the url conf and the middleware.

The modules ``test_api_v1_views_*`` test each view module in detail. This module
holds :class:`AccountApiTestMixin`, which they share, and a smoke test of every
route of ``am.apps.account.api.v1.urls``.
"""

from http import HTTPStatus

from django.test import Client
from django.urls import reverse

from am.apps.account.models import Account, PaymentMethod, User, UserProfile
from am.common.utils import hash_factory

from .factories import (
    factory_account_teardown,
    mortal_user_factory,
    payment_method_factory,
    payment_method_factory_teardown,
)
from .mixins import TestAccountMixin


class AccountApiTestMixin:
    """
    Fixtures for testing the account api, for a subclass of :class:`TestAccountMixin`.

    Adds, in ``setUpClass``:

    - ``staff_user``: a staff user who is not a superuser, in ``cls.account``.
    - ``other_user``, ``other_account``: a user of a second Account.
    - ``payment_method``: a PaymentMethod of ``cls.account``.
    - ``other_payment_method``: a PaymentMethod of ``other_account``.

    and deletes them in ``tearDownClass``.
    """

    namespace = "api:v1:account:"

    staff_user: User
    staff_user_profile: UserProfile
    other_user: User
    other_account: Account
    other_user_profile: UserProfile
    payment_method: PaymentMethod
    other_payment_method: PaymentMethod

    @classmethod
    def setUpClass(cls):
        """Create the staff user, the second Account, and the PaymentMethods."""
        super().setUpClass()  # type: ignore[misc]
        cls.staff_user, cls.staff_user_profile = cls.create_staff_user(cls.account)  # type: ignore[attr-defined]
        cls.other_user, cls.other_account, cls.other_user_profile = mortal_user_factory()
        cls.payment_method = payment_method_factory(cls.account)  # type: ignore[attr-defined]
        cls.other_payment_method = payment_method_factory(cls.other_account)

    @classmethod
    def tearDownClass(cls):
        """Delete what ``setUpClass`` created."""
        payment_method_factory_teardown(PaymentMethod.objects.filter(pk=cls.payment_method.pk).first())
        payment_method_factory_teardown(PaymentMethod.objects.filter(pk=cls.other_payment_method.pk).first())
        factory_account_teardown(user=cls.staff_user, account=None, user_profile=None)  # type: ignore[arg-type]
        factory_account_teardown(user=cls.other_user, account=cls.other_account, user_profile=None)  # type: ignore[arg-type]
        super().tearDownClass()  # type: ignore[misc]

    @staticmethod
    def create_staff_user(account: Account) -> tuple[User, UserProfile]:
        """
        Create a staff user who is not a superuser, with a UserProfile in ``account``.

        :param account: The Account.
        :returns: The User and its UserProfile.
        """
        slug = hash_factory()
        user = User.objects.create_user(
            username=f"test_staff_user_{slug}",
            email=f"test-staff-{slug}@example.com",
            password="12345",
            is_staff=True,
        )
        return user, UserProfile.objects.create(user=user, account=account, is_test=True)

    def url(self, name: str, *args) -> str:
        """
        Reverse an account api url name.

        :param name: The url name, without the namespace.
        :param args: The url's arguments.
        :returns: The path.
        """
        return reverse(self.namespace + name, args=list(args))

    def client_without_profile(self) -> Client:
        """
        A test client signed in as a staff user who has no UserProfile.

        Signing in creates a UserProfile in the default Account (see
        ``am.apps.account.receivers``), so the profiles are deleted after signing in.
        The user is deleted when the test ends.

        :returns: The client.
        """
        user, _ = self.create_staff_user(self.account)  # type: ignore[attr-defined]
        self.addCleanup(user.delete)  # type: ignore[attr-defined]
        client = self.client_for(user)
        UserProfile.objects.filter(user=user).delete()
        return client

    @staticmethod
    def client_for(user) -> Client:
        """
        A test client signed in as ``user``.

        :param user: The user, or None for an anonymous client.
        :returns: The client.
        """
        client = Client()
        if user is not None:
            client.force_login(user)
        return client


class TestAccountApiUrls(AccountApiTestMixin, TestAccountMixin):
    """Smoke test of every account api route, as a superuser."""

    def setUp(self):
        """Sign in as the superuser."""
        super().setUp()
        self.client = self.client_for(self.admin_user)

    def test_account_list_view(self):
        """The account list holds the test Account."""
        response = self.client.get(self.url("account_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        account_numbers = [account["accountNumber"] for account in response.json()]
        self.assertIn(self.account.account_number, account_numbers)

    def test_account_view(self):
        """The account view returns the test Account in camelCase."""
        response = self.client.get(self.url("account_view", self.account.id))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["companyName"], self.account.company_name)
        self.assertEqual(response.json()["accountNumber"], self.account.account_number)

    def test_account_users_list_view(self):
        """The user list holds the superuser."""
        response = self.client.get(self.url("account_users_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        emails = [user["email"] for user in response.json()]
        self.assertIn(self.admin_user.email, emails)

    def test_account_user_view(self):
        """The user view returns the superuser."""
        response = self.client.get(self.url("account_user_view", self.admin_user.id))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["username"], self.admin_user.username)
        self.assertEqual(response.json()["email"], self.admin_user.email)

    def test_account_payment_methods_list_view(self):
        """The payment method list holds the test PaymentMethod."""
        response = self.client.get(self.url("account_payment_methods_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        names = [payment_method["name"] for payment_method in response.json()]
        self.assertIn(self.payment_method.name, names)

    def test_account_payment_method_view(self):
        """The payment method view returns the test PaymentMethod in camelCase."""
        response = self.client.get(self.url("account_payment_method_view", self.payment_method.id))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["name"], self.payment_method.name)
        self.assertEqual(data["cardType"], self.payment_method.card_type)
        self.assertEqual(data["cardLast4"], str(self.payment_method.card_last_4))
        self.assertEqual(data["isDefault"], self.payment_method.is_default)

    def test_subscription_status_view(self):
        """The subscription status view answers 403 for an unknown user."""
        response = self.client_for(None).get(
            self.url("subscription_status_view"), HTTP_X_CLIENT_USERNAME="no-such-user"
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_anonymous_request_is_refused(self):
        """An anonymous request to an admin route is redirected to the admin sign-in page."""
        response = self.client_for(None).get(self.url("account_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/admin/login/", response["Location"])

    def test_non_staff_request_is_refused(self):
        """A request by a user who is not staff is redirected to the admin sign-in page."""
        response = self.client_for(self.non_admin_user).get(self.url("account_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/admin/login/", response["Location"])
