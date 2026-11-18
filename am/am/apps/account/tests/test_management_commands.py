"""Test the account app's manage.py commands."""

from io import StringIO
from unittest import mock

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.management import call_command

from am.apps.account.management.commands.create_user import Command as CreateUserCommand
from am.apps.account.models import Account, AccountContact, User, UserProfile
from am.apps.account.tests.mixins import AccountTestCase
from am.common.conf import am_settings
from am.common.const import ACCOUNT_ACCOUNT_NUMBER, ACCOUNT_CUSTOMER_SUPPORT_EMAIL
from am.common.exceptions import AMValueError
from am.lib import json
from am.lib.drf.models import AMAuthToken


class CommandTestCase(AccountTestCase):
    """Run commands with captured output, against an account with one (test) user."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Commands Co")
        # staff, because only staff users may own api keys
        cls.user = User.objects.create_user(
            username="commands_user",
            email="commands_user@example.com",
            first_name="Com",
            last_name="Mands",
            is_staff=True,
        )
        cls.user_profile = UserProfile.objects.create(user=cls.user, account=cls.account, is_test=True)

    def call(self, name: str, *args, **kwargs) -> str:
        """Run a command and return its output."""
        out = StringIO()
        call_command(name, *args, stdout=out, **kwargs)
        return out.getvalue()


class TestAddAccountContact(CommandTestCase):
    """Test manage.py add_account_contact."""

    def test_add_by_account_number(self):
        """A new email address is added to the account's contacts."""
        output = self.call("add_account_contact", account_number=self.account.account_number, email="new@example.com")
        self.assertTrue(AccountContact.objects.filter(account=self.account, email="new@example.com").exists())
        self.assertIn("Account Contact new@example.com added", output)

    def test_add_by_company_name_already_exists(self):
        """An existing contact is reported, not duplicated."""
        output = self.call("add_account_contact", company_name="Commands Co", username="commands_user")
        self.assertIn("already exists", output)
        self.assertEqual(AccountContact.objects.filter(account=self.account, email=self.user.email).count(), 1)

    def test_account_not_found(self):
        """An unknown account number or company name exits with an error."""
        with self.assertRaises(SystemExit):
            self.call("add_account_contact", account_number="0000-0000-0009", email="x@example.com")
        with self.assertRaises(SystemExit):
            self.call("add_account_contact", company_name="Nobody Co", email="x@example.com")

    def test_account_not_found_without_exit(self):
        """Nothing is added for an unknown account, even if the failure handler returns."""
        with mock.patch("am.lib.django.management.base.sys.exit"):
            self.call("add_account_contact", account_number="0000-0000-0009", email="x@example.com")
            self.call("add_account_contact", company_name="Nobody Co", email="x@example.com")
        self.assertFalse(AccountContact.objects.filter(email="x@example.com").exists())

    def test_account_is_required(self):
        """Neither an account number nor a company name raises."""
        with self.assertRaises(AMValueError):
            self.call("add_account_contact", email="x@example.com")


class TestDeleteAccountContact(CommandTestCase):
    """Test manage.py delete_account_contact."""

    def test_delete_by_account_number(self):
        """A contact is removed from the account."""
        AccountContact.objects.create(
            account=self.account, first_name="D", last_name="D", email="d@example.com", is_test=True
        )
        output = self.call("delete_account_contact", account_number=self.account.account_number, email="d@example.com")
        self.assertFalse(AccountContact.objects.filter(account=self.account, email="d@example.com").exists())
        self.assertIn("removed", output)

    def test_delete_by_company_name_and_username(self):
        """A user's contact is found by username."""
        self.call("delete_account_contact", company_name="Commands Co", username="commands_user")
        self.assertFalse(AccountContact.objects.filter(account=self.account, email=self.user.email).exists())

    def test_not_found(self):
        """An unknown account or contact is reported."""
        output = self.call("delete_account_contact", account_number="0000-0000-0009", email="d@example.com")
        self.assertIn("Account 0000-0000-0009 not found.", output)
        output = self.call("delete_account_contact", company_name="Nobody Co", email="d@example.com")
        self.assertIn("Account Nobody Co not found.", output)
        output = self.call("delete_account_contact", company_name="Commands Co", email="nobody@example.com")
        self.assertIn("Account Contact nobody@example.com not found", output)

    def test_account_is_required(self):
        """Neither an account number nor a company name raises."""
        with self.assertRaises(AMValueError):
            self.call("delete_account_contact", email="d@example.com")


class TestCreateAccount(CommandTestCase):
    """Test manage.py create_account."""

    def test_create_account(self):
        """An account is created with a generated or a given account number, once."""
        output = self.call("create_account", company_name="New Co")
        self.assertIn("Created account", output)
        self.assertTrue(Account.objects.filter(company_name="New Co").exists())

        output = self.call("create_account", company_name="Numbered Co", account_number="1111-2222-3333")
        self.assertTrue(Account.objects.filter(company_name="Numbered Co", account_number="1111-2222-3333").exists())
        output = self.call("create_account", company_name="Numbered Co", account_number="1111-2222-3333")
        self.assertIn("Account already exists", output)


class TestCreateAccountAdmin(CommandTestCase):
    """Test manage.py create_account_admin, which the deployment's init job runs."""

    def test_fresh_platform(self):
        """The platform account, superuser, profile and an api key are created; the key is not printed."""
        Account.objects.filter(account_number=ACCOUNT_ACCOUNT_NUMBER).delete()
        output = self.call("create_account_admin", username="cmd_admin", email="cmd_admin@example.com", password="pw")

        account = Account.objects.get(account_number=ACCOUNT_ACCOUNT_NUMBER)
        self.assertTrue(account.is_default_account)
        user = User.objects.get(username="cmd_admin")
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(user.check_password("pw"))
        self.assertTrue(UserProfile.objects.filter(user=user, account=account).exists())
        token = AMAuthToken.objects.get(user=user)
        self.assertIn(str(token.key_id), output)
        self.assertIn("Created superuser", output)
        self.assertNotIn("API key: ", output)

        # running it again (every deployment) changes nothing
        output = self.call("create_account_admin", username="cmd_admin", email="cmd_admin@example.com", password="pw")
        self.assertIn("User cmd_admin updated.", output)
        self.assertEqual(AMAuthToken.objects.filter(user=user).count(), 1)

    def test_credentials_from_the_environment(self):
        """
        Without options, the credentials come from AM_ADMIN_USERNAME, AM_ADMIN_EMAIL and AM_ADMIN_PASSWORD.

        The Helm chart's init job runs it this way, so the password is on no command line.
        """
        Account.objects.filter(account_number=ACCOUNT_ACCOUNT_NUMBER).delete()
        environment = {
            "AM_ADMIN_USERNAME": "env_admin",
            "AM_ADMIN_EMAIL": "env_admin@example.com",
            "AM_ADMIN_PASSWORD": "env-pw",
        }
        with mock.patch.dict("os.environ", environment):
            self.call("create_account_admin")
        user = User.objects.get(username="env_admin")
        self.assertEqual(user.email, "env_admin@example.com")
        self.assertTrue(user.check_password("env-pw"))
        self.assertTrue(user.is_superuser)

    def test_generated_password_and_support_contact(self):
        """Without a password one is generated; an account without a primary contact gets the support one."""
        Account.objects.filter(account_number=ACCOUNT_ACCOUNT_NUMBER).delete()
        self.call("create_account_admin", username="cmd_admin2", email="cmd_admin2@example.com")
        self.assertTrue(User.objects.get(username="cmd_admin2").has_usable_password())
        account = Account.objects.get(account_number=ACCOUNT_ACCOUNT_NUMBER)
        # the admin's own contact is the account's primary contact
        self.assertEqual(AccountContact.objects.get(account=account, is_primary=True).email, "cmd_admin2@example.com")
        self.send_email.reset_mock()

        AccountContact.objects.filter(account=account).delete()
        self.call("create_account_admin", username="cmd_admin2", email="cmd_admin2@example.com")
        support = AccountContact.objects.get(account=account, is_primary=True)
        self.assertEqual(support.email, ACCOUNT_CUSTOMER_SUPPORT_EMAIL)
        sent_to = [c.kwargs["to"] for c in self.send_email.call_args_list]
        self.assertNotIn(ACCOUNT_CUSTOMER_SUPPORT_EMAIL, sent_to)


class TestCreateApiKey(CommandTestCase):
    """Test manage.py create_api_key."""

    def test_account_or_username_is_required(self):
        """Without an account number or a username, nothing is created."""
        output = self.call("create_api_key")
        self.assertIn("You must provide an account number or a username", output)
        self.assertFalse(AMAuthToken.objects.exists())

    def test_by_username(self):
        """The key belongs to the user, and is printed once."""
        output = self.call("create_api_key", username="commands_user", description="test key")
        token = AMAuthToken.objects.get(user=self.user)
        self.assertEqual(token.name, f"{self.account.account_number}.commands_user")
        self.assertEqual(token.description, "test key")
        self.assertIn("API key: ", output)

    def test_by_username_and_account_number(self):
        """A user and their account give a key for that user."""
        self.call("create_api_key", username="commands_user", account_number=self.account.account_number)
        self.assertTrue(AMAuthToken.objects.filter(user=self.user).exists())

    def test_by_account_number(self):
        """An account number alone gives a key for the account's admin user."""
        self.call("create_api_key", account_number=self.account.account_number)
        token = AMAuthToken.objects.get()
        self.assertTrue(token.user.is_staff)
        self.assertTrue(UserProfile.objects.filter(user=token.user, account=self.account).exists())

    def test_user_without_profile(self):
        """A user without a profile gets no key."""
        User.objects.create_user(username="commands_solo", email="solo@example.com")
        output = self.call("create_api_key", username="commands_solo")
        self.assertIn("User commands_solo does not have a user profile", output)
        self.assertFalse(AMAuthToken.objects.exists())


class TestCreateUser(CommandTestCase):
    """Test manage.py create_user, which the deployment's init job runs."""

    options = {"first_name": "Staff", "last_name": "User", "email": "staff@example.com"}

    def test_create_user(self):
        """A new user is created in the account, and emailed their credentials."""
        output = self.call(
            "create_user",
            account_number=self.account.account_number,
            username="cmd_staff",
            password="pw-1",
            admin=True,
            **self.options,
        )
        user = User.objects.get(username="cmd_staff")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.check_password("pw-1"))
        self.assertTrue(UserProfile.objects.filter(user=user, account=self.account).exists())
        contact = AccountContact.objects.get(account=self.account, email="staff@example.com")
        self.assertEqual((contact.first_name, contact.last_name), ("Staff", "User"))
        self.assertIn("User cmd_staff staff@example.com has been created.", output)
        # no email: Smarter welcomes its users, and a password is never emailed.
        self.send_email.assert_not_called()

    def test_generated_password(self):
        """Without a password, a new user gets a generated one."""
        self.call("create_user", account_number=self.account.account_number, username="cmd_gen", **self.options)
        self.assertTrue(User.objects.get(username="cmd_gen").has_usable_password())
        self.assertFalse(User.objects.get(username="cmd_gen").is_staff)

    def test_existing_user_password_is_changed_but_not_printed(self):
        """Re-running with a password changes it, and the password is not written to the log."""
        self.call(
            "create_user",
            account_number=self.account.account_number,
            username="cmd_staff",
            password="pw-1",
            **self.options,
        )
        output = self.call(
            "create_user",
            account_number=self.account.account_number,
            username="cmd_staff",
            password="pw-2",
            **self.options,
        )
        self.assertTrue(User.objects.get(username="cmd_staff").check_password("pw-2"))
        self.assertIn("Updated password for cmd_staff.", output)
        self.assertNotIn("pw-2", output)

    def test_existing_user_password_is_kept_without_one(self):
        """Re-running without a password leaves the existing password alone."""
        self.call(
            "create_user",
            account_number=self.account.account_number,
            username="cmd_staff",
            password="pw-1",
            **self.options,
        )
        self.call("create_user", account_number=self.account.account_number, username="cmd_staff", **self.options)
        self.assertTrue(User.objects.get(username="cmd_staff").check_password("pw-1"))

    def test_missing_contact_is_created(self):
        """A user whose contact was removed gets it back."""
        args = {"account_number": self.account.account_number, "username": "cmd_staff", "password": "pw"}
        self.call("create_user", **args, **self.options)
        AccountContact.objects.filter(account=self.account, email="staff@example.com").delete()
        output = self.call("create_user", **args, **self.options)
        self.assertIn("Account contact created for Staff User", output)
        self.assertTrue(AccountContact.objects.filter(account=self.account, email="staff@example.com").exists())

    def test_change_password_unknown_user(self):
        """Change_password() reports an unknown user."""
        out = StringIO()
        command = CreateUserCommand(stdout=out)
        self.assertIsNone(command.change_password("cmd_nobody", "pw"))
        self.assertIn("User cmd_nobody does not exist.", out.getvalue())


class TestDumpDjangoSettings(CommandTestCase):
    """Test manage.py dump_django_settings."""

    def test_dump(self):
        """Every upper-case setting is written to the command's output."""
        output = self.call("dump_django_settings")
        self.assertIn("INSTALLED_APPS: ", output)
        self.assertIn("TIME_ZONE: UTC", output)


class TestGetAccounts(CommandTestCase):
    """Test manage.py get_accounts."""

    def test_all_accounts(self):
        """Every account is listed as JSON."""
        output = self.call("get_accounts")
        self.assertIn(self.account.account_number, output)

    def test_filtered_accounts(self):
        """A regular expression filters the accounts by company name."""
        Account.objects.create(company_name="Other Co")
        output = self.call("get_accounts", "^Commands")
        # the JSON list sits between the command's header and footer lines
        listing = output[output.index("\n[") + 1 : output.rindex("]") + 1]
        names = [account.get("companyName", account.get("company_name")) for account in json.loads(listing)]
        self.assertEqual(names, ["Commands Co"])

    def test_invalid_regex(self):
        """An invalid regular expression raises."""
        with self.assertRaises(ValidationError):
            self.call("get_accounts", "[unclosed")


class TestInitializeSite(CommandTestCase):
    """Test manage.py initialize_site, which the deployment's init job runs."""

    def test_initialize_site(self):
        """The two Django sites are set to the environment's domains."""
        self.call("initialize_site")
        self.assertEqual(Site.objects.get(id=1).domain, am_settings.environment_domain)
        self.assertEqual(Site.objects.get(id=2).domain, am_settings.environment_api_domain)
