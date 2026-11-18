"""
Test api/v1/ base class.

We have somewhere in the neighborhood of 75 api endpoints to test, so we want
ensure that:
- our setUp and tearDown methods are as efficient as possible.
- we are authenticating our http requests properly and consistently.
"""

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings

from am.apps.account.mixins import AccountMixin
from am.apps.account.models import Account, User, UserProfile
from am.apps.account.tests.factories import mortal_user_factory
from am.apps.account.tests.mixins import AccountTestCase
from am.apps.account.utils import (
    get_cached_admin_user_for_account,
    get_cached_user_profile,
)
from am.common.classes import AMHelperMixin
from am.common.exceptions import AMBusinessRuleViolation
from am.lib.drf.models import AMAuthToken
from am.lib.unittest.base_classes import AMTestBase


class TestAccountMixin(AMTestBase):
    """Test AccountMixin."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.mortal_user, cls.account, cls.user_profile = mortal_user_factory()
        cls.admin_user = get_cached_admin_user_for_account(cls.account)
        cls.other_user, cls.other_account, cls.other_user_profile = mortal_user_factory()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        instance = cls()
        # tear down the user, account, and user_profile
        try:
            if instance.user_profile:
                instance.user_profile.delete()
        except UserProfile.DoesNotExist:
            pass
        try:
            if instance.mortal_user:
                instance.mortal_user.delete()
        except User.DoesNotExist:
            pass

        # tear down the admin user
        try:
            up = get_cached_user_profile(user=cls.admin_user)
            if up:
                up.delete()
        except UserProfile.DoesNotExist:
            pass
        try:
            if cls.admin_user:
                cls.admin_user.delete()
        except User.DoesNotExist:
            pass

        try:
            if instance.account:
                instance.account.delete()
        except Account.DoesNotExist:
            pass
        # tear down the other user, account, and user_profile
        try:
            if instance.other_user_profile:
                instance.other_user_profile.delete()
        except UserProfile.DoesNotExist:
            pass
        try:
            if instance.other_user:
                instance.other_user.delete()
        except User.DoesNotExist:
            pass
        try:
            if instance.other_account:
                instance.other_account.delete()
        except Account.DoesNotExist:
            pass

    def test_initializations(self) -> None:
        """Test instantiation with all arguments."""
        # verify that the user, account, and user_profile are what we think they are
        instance = AccountMixin(user=self.mortal_user, account=self.account)
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # ditto for the other user, account, and user_profile
        other_instance = AccountMixin(user=self.other_user, account=self.other_account)
        self.assertEqual(other_instance.user, self.other_user)
        self.assertEqual(other_instance.account, self.other_account)
        self.assertEqual(other_instance.user_profile, self.other_user_profile)

        # verify that the user, account are different from the other_user, other_account
        self.assertNotEqual(self.mortal_user, self.other_user)
        self.assertNotEqual(self.account, self.other_account)
        self.assertNotEqual(self.user_profile, self.other_user_profile)
        self.assertNotEqual(instance.user, other_instance.user)
        self.assertNotEqual(instance.account, other_instance.account)
        self.assertNotEqual(instance.user_profile, other_instance.user_profile)

        # verify that the admin user is what we think it is and that it's profile is cached
        # and that it's associated with the same account as user.
        self.assertIsNotNone(self.admin_user)
        admin_user_profile = get_cached_user_profile(user=self.admin_user, account=self.account)
        self.assertIsNotNone(admin_user_profile)
        if not isinstance(admin_user_profile, UserProfile):
            self.fail("Admin user profile should not be None")
        self.assertEqual(admin_user_profile.user, self.admin_user)
        self.assertEqual(admin_user_profile.account, self.account)

    def test_get_cached_admin_user_for_account(self) -> None:
        """Test get_cached_admin_user_for_account."""
        admin_user = get_cached_admin_user_for_account(self.account)
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user, self.admin_user)

    def test_get_cached_user_profile(self) -> None:
        """Test get_cached_user_profile."""
        user_profile = get_cached_user_profile(user=self.mortal_user, account=self.account)
        self.assertIsNotNone(user_profile)
        self.assertEqual(user_profile, self.user_profile)

        # get the profile without providing an account
        user_profile = get_cached_user_profile(user=self.mortal_user)
        self.assertIsNotNone(user_profile)
        self.assertEqual(user_profile, self.user_profile)

        # get the admin user profile
        user_profile = get_cached_user_profile(user=self.admin_user)
        self.assertIsNotNone(user_profile)
        self.assertEqual(user_profile.user, self.admin_user)  # type: ignore[return-value]

    def test_empty_initialization(self) -> None:
        """Test instantiation with no arguments."""
        instance = AccountMixin()
        self.assertIsNone(instance.user)
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user_profile)

    def test_user_initialization(self) -> None:
        """
        Test instantiation with a user.

        Mixin should set account and
        user_profile based on the user.
        """
        instance = AccountMixin(user=self.mortal_user)
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

    def test_unset_user(self) -> None:
        """Test setting user to None."""
        instance = AccountMixin(user=self.mortal_user)
        self.assertEqual(instance.user, self.mortal_user)
        # force lazy instantiations of account and user_profile.
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # unset the user but leave the account unchanged.
        # should reinitialize with the admin user.
        instance.user = None
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user_profile)

        # unset both the user and account.
        # should unset everything.
        instance.user = None
        instance.account = None
        self.assertIsNone(instance.user)
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user_profile)

    def test_unset_account(self) -> None:
        """Test setting account to None."""
        instance = AccountMixin(user=self.mortal_user)
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # should unset the account, but leave the user unchanged.
        # should reinitialize the account and user_profile based on the user.
        instance.account = None
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertIsNotNone(instance.user_profile)
        self.assertEqual(instance.user_profile, self.user_profile)

    def test_unset_user_profile(self) -> None:
        """Test setting user_profile to None."""
        instance = AccountMixin(user=self.mortal_user)
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # .1) unset the user_profile, but leave the user and account unchanged.
        # should reinitialize the user_profile based on the user.
        instance.user_profile = None
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # .2) unset the user_profile and user, but leave the account unchanged.
        instance.user_profile = None
        instance.account = None

        # ensure that user is still set.
        self.assertEqual(instance.user, self.mortal_user)

        # should reinitialize the account and user_profile based on the user.
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)

        # .3) unset the user_profile and account, but leave the user unchanged.
        instance.user_profile = None
        instance.account = None

        # ensure that account is still set.
        self.assertIsNotNone(instance.account)

    def test_set_account(self) -> None:
        """
        Test setting account.

        Should set the admin user and user_profile
        """
        instance = AccountMixin(account=self.account)
        self.assertIsNotNone(self.account)
        self.assertIsNotNone(instance.account)
        self.assertEqual(instance.account, self.account)

        # verify that neither the user nor the user_profile are set.
        self.assertIsNone(instance.user)
        self.assertIsNone(instance.user_profile)

    def test_invalid_user_assignment(self) -> None:
        """Test setting an invalid user."""
        instance = AccountMixin(account=self.account)
        with self.assertRaises(AMBusinessRuleViolation):
            instance.user = self.other_user

    def test_invalid_account_assignment(self) -> None:
        """Test setting an invalid account."""
        instance = AccountMixin(user=self.mortal_user)

        # verify that the user and account are what we think they are
        self.assertEqual(instance.user, self.mortal_user)
        self.assertEqual(instance.account, self.account)

        # ensure that the other account is not the same as the base account
        self.assertNotEqual(self.account, self.other_account)

        # try to set the account to the other account which
        # should raise an exception.
        with self.assertRaises(AMBusinessRuleViolation):
            instance.account = self.other_account

    def test_account_number(self) -> None:
        """Test account_number."""
        instance = AccountMixin(account_number=self.account.account_number)
        self.assertIsNotNone(instance.account)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.account_number, self.account.account_number)

        instance.account = None
        self.assertIsNone(instance.account)

    def test_unset_account_number(self) -> None:
        """Test setting account_number to None."""
        instance = AccountMixin(account_number=self.account.account_number)
        self.assertIsNotNone(instance.account)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.account_number, self.account.account_number)

        instance.account_number = None
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.account_number)


class Unreadable:
    """An object whose truth value can't be read, for the properties' defensive paths."""

    def __bool__(self):
        raise RuntimeError("unreadable")


@override_settings(ALLOWED_HOSTS=["*"])
class TestAccountMixinSources(AccountTestCase):
    """Test how AccountMixin resolves its user and account from requests, api tokens and urls."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Mixin Co")
        cls.user = User.objects.create_user(username="mixin_user", email="mixin@example.com", is_staff=True)
        cls.user_profile = UserProfile.objects.create(user=cls.user, account=cls.account, is_test=True)
        cls.other_account = Account.objects.create(company_name="Mixin Other Co")

    def request(self, host: str = "testserver", user=None):
        """Return a GET request to host, for user."""
        request = RequestFactory().get("/some/path/", HTTP_HOST=host)
        request.user = user or AnonymousUser()
        return request

    def test_request_with_user(self):
        """A request's user, given positionally, sets the user, account and profile."""
        instance = AccountMixin(self.request(user=self.user))
        self.assertEqual(instance.user, self.user)
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user_profile, self.user_profile)
        self.assertTrue(instance.is_accountmixin_ready)
        self.assertTrue(instance.ready)
        self.assertTrue(instance.is_authenticated)
        self.assertIn("mixin@example.com", str(instance))

    def test_request_with_account_number_in_url(self):
        """An anonymous request to a url with an account number sets the account."""
        host = f"hr.{self.account.account_number}.api.example.com"
        instance = AccountMixin(request=self.request(host=host))
        self.assertEqual(instance.account, self.account)
        self.assertIsNone(instance.user)
        self.assertFalse(instance.is_accountmixin_ready)
        self.assertFalse(instance.is_authenticated)

    def test_request_without_user_or_account(self):
        """An anonymous request to a plain url sets nothing."""
        instance = AccountMixin(request=self.request(host="www.example.com"))
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user)
        self.assertFalse(instance.ready)

    def test_request_with_unresolvable_user(self):
        """A request whose user isn't a Django user has no account or profile."""
        instance = AccountMixin(request=self.request(host="www.example.com", user=SimpleNamespace(id=None)))
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user_profile)

    def test_api_token(self):
        """A valid api token sets the user and account; an invalid one sets nothing."""
        _, key = AMAuthToken.objects.create(user=self.user, name="mixin-key")  # type: ignore[misc]
        instance = AccountMixin(api_token=key.encode())
        self.assertEqual(instance.user, self.user)
        self.assertEqual(instance.account, self.account)

        instance = AccountMixin(request=self.request(host="www.example.com"), api_token=b"not-a-valid-token")
        self.assertIsNone(instance.user)

    def test_user_without_account(self):
        """A user without a profile has no account."""
        solo = User.objects.create_user(username="mixin_solo", email="solo@example.com")
        instance = AccountMixin(user=solo)
        self.assertIsNone(instance.account)
        self.assertIsNone(instance.user_profile)

    def test_account_number_setter(self):
        """Setting the account number sets the account; clearing it clears account and profile."""
        instance = AccountMixin()
        instance.account_number = self.account.account_number
        self.assertEqual(instance.account, self.account)
        instance.account_number = "0000-0000-0042"  # unknown: the account is unchanged
        self.assertEqual(instance.account, self.account)
        instance.account_number = None
        self.assertIsNone(instance.account)

    def test_user_profile_setter(self):
        """Setting a profile sets its user and account."""
        instance = AccountMixin()
        instance.user_profile = self.user_profile
        self.assertEqual(instance.user, self.user)
        self.assertEqual(instance.account, self.account)

    def test_lazy_account_and_user_from_profile(self):
        """With only a profile, the account and user are read from it."""
        instance = AccountMixin()
        instance._user_profile = self.user_profile  # pylint: disable=protected-access
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user, self.user)

    def test_user_profile_for_wrong_account(self):
        """A user who doesn't belong to the account raises when the profile is read."""
        instance = AccountMixin()
        instance._user = self.user  # pylint: disable=protected-access
        instance._account = self.other_account  # pylint: disable=protected-access
        with self.assertRaises(AMBusinessRuleViolation):
            _ = instance.user_profile

    def test_unreadable_values(self):
        """Errors reading the cached account or user are logged and give None."""
        instance = AccountMixin()
        instance._account = Unreadable()  # type: ignore[assignment] # pylint: disable=protected-access
        self.assertIsNone(instance.account)
        instance._user = Unreadable()  # type: ignore[assignment] # pylint: disable=protected-access
        self.assertIsNone(instance.user)

    def test_type_errors_are_logged(self):
        """A TypeError looking up the profile, e.g. for a lazy anonymous user, leaves the profile unset."""
        instance = AccountMixin(user=self.user)
        with mock.patch("am.apps.account.mixins.get_cached_user_profile", side_effect=TypeError("lazy")):
            instance.account = self.account
            instance._user_profile = None  # pylint: disable=protected-access
            instance.user = self.user
        self.assertEqual(instance.account, self.account)
        self.assertEqual(instance.user, self.user)

    def test_ready_depends_on_super(self):
        """Ready is False when the parent class isn't ready."""
        instance = AccountMixin(user=self.user)
        with mock.patch.object(AMHelperMixin, "ready", new_callable=mock.PropertyMock, return_value=False):
            self.assertFalse(instance.ready)

    def test_to_json(self):
        """To_json() serializes the account, user and profile."""
        data = AccountMixin(user=self.user).to_json()
        self.assertTrue(data["ready"])
        self.assertIsNotNone(data["account"])
        self.assertIsNotNone(data["user"])
        self.assertIsNotNone(data["user_profile"])
        self.assertEqual(data["class_name"], "AccountMixin")

        data = AccountMixin().to_json()
        self.assertIsNone(data["account"])
        self.assertIsNone(data["user"])
        self.assertIsNone(data["user_profile"])
