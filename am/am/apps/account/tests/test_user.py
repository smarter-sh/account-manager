"""Test UserProfile, the link between a user and an account."""

from unittest import mock

from am.apps.account.models import Account, AccountContact, User, UserProfile
from am.apps.account.signals import new_user_created
from am.apps.account.tests.mixins import AccountTestCase
from am.common.exceptions import AMValueError


class TestUserProfile(AccountTestCase):
    """Test UserProfile."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Users Co")
        cls.first_user = User.objects.create_user(
            username="users_first", email="first@example.com", first_name="First", last_name="User"
        )
        cls.second_user = User.objects.create_user(username="users_second", email="second@example.com")

    def test_first_profile_is_primary_contact(self):
        """The account's first user becomes its primary contact; later ones are ordinary contacts."""
        UserProfile.objects.create(user=self.first_user, account=self.account, is_test=True)
        UserProfile.objects.create(user=self.second_user, account=self.account, is_test=True)

        first = AccountContact.objects.get(account=self.account, email="first@example.com")
        self.assertTrue(first.is_primary)
        self.assertEqual((first.first_name, first.last_name), ("First", "User"))
        self.assertTrue(first.is_test)

        second = AccountContact.objects.get(account=self.account, email="second@example.com")
        self.assertFalse(second.is_primary)
        # a user without a name gets a placeholder one
        self.assertEqual((second.first_name, second.last_name), ("account", "contact"))

    def test_add_to_account_contacts_changes_primary(self):
        """Add_to_account_contacts() moves the primary flag on and off."""
        profile = UserProfile.objects.create(user=self.first_user, account=self.account, is_test=True)
        profile.add_to_account_contacts(is_primary=False)
        self.assertFalse(AccountContact.objects.get(account=self.account, email="first@example.com").is_primary)
        profile.add_to_account_contacts(is_primary=True)
        self.assertTrue(AccountContact.objects.get(account=self.account, email="first@example.com").is_primary)

    def test_new_profile_sends_signal_once(self):
        """A new profile sends new_user_created; an update does not."""
        receiver = mock.MagicMock()
        new_user_created.connect(receiver, dispatch_uid="test_new_profile_sends_signal_once")
        self.addCleanup(new_user_created.disconnect, dispatch_uid="test_new_profile_sends_signal_once")

        profile = UserProfile.objects.create(user=self.first_user, account=self.account, is_test=True)
        receiver.assert_called_once()
        self.assertEqual(receiver.call_args.kwargs["user_profile"], profile)
        profile.save()
        receiver.assert_called_once()

    def test_user_and_account_are_required(self):
        """A profile without a user or an account raises AMValueError."""
        with self.assertRaises(AMValueError):
            UserProfile(account=self.account).save()
        with self.assertRaises(AMValueError):
            UserProfile(user=self.first_user).save()

    def test_str(self):
        """A profile is shown as company name and email, or username without one."""
        profile = UserProfile.objects.create(user=self.first_user, account=self.account, is_test=True)
        self.assertEqual(str(profile), "Users Co-first@example.com")
        self.first_user.email = ""
        self.assertEqual(str(profile), "Users Co-users_first")
