"""Test the platform key authentication (``am.apps.account.api.v1.authentication``)."""

from django.core.management import call_command
from django.test import RequestFactory
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from am.apps.account.api.v1.authentication import (
    PLATFORM_AUTH_SCHEME,
    PlatformClientAuthentication,
    PlatformClientUser,
)
from am.apps.account.models import PlatformClient
from am.common.exceptions import AMValueError

from .mixins import AccountTestCase


class TestPlatformClient(AccountTestCase):
    """Test the PlatformClient model: its key is shown once, stored as a digest, and checked."""

    def test_key_is_stored_only_as_a_digest(self):
        """The key itself is in no column."""
        client, key = PlatformClient.create_with_key("Platform.Example.COM", description="test")
        self.assertEqual(client.host_name, "platform.example.com")
        self.assertEqual(client.key_prefix, key[: PlatformClient.KEY_PREFIX_LENGTH])
        self.assertEqual(client.key_digest, PlatformClient.digest(key))
        self.assertNotIn(key, client.key_digest)
        self.assertEqual(str(client), "platform.example.com (active)")

    def test_authenticate_records_use(self):
        """A right key returns its platform and sets last_used_at; a wrong one returns None."""
        client, key = PlatformClient.create_with_key("platform.example.com")
        self.assertEqual(PlatformClient.authenticate(key), client)
        client.refresh_from_db()
        self.assertIsNotNone(client.last_used_at)
        for wrong in ("", "short", key[:-1] + ("x" if key[-1] != "x" else "y")):
            with self.subTest(wrong):
                self.assertIsNone(PlatformClient.authenticate(wrong))

    def test_inactive_platform_doesnt_authenticate(self):
        """A deactivated platform's key returns None."""
        client, key = PlatformClient.create_with_key("platform.example.com")
        client.is_active = False
        client.save()
        self.assertIsNone(PlatformClient.authenticate(key))
        self.assertEqual(str(client), "platform.example.com (inactive)")

    def test_invalid_host_name_is_refused(self):
        """The host name must be a valid host name."""
        with self.assertRaises(AMValueError):
            PlatformClient.create_with_key("not a host name")


class TestPlatformClientAuthentication(AccountTestCase):
    """Test PlatformClientAuthentication, the DRF authentication class."""

    def setUp(self):
        super().setUp()
        self.client_record, self.key = PlatformClient.create_with_key("platform.example.com")
        self.auth = PlatformClientAuthentication()

    def request(self, authorization=None) -> Request:
        """
        Build a DRF request.

        :param authorization: The Authorization header, or None.
        :returns: The request.
        """
        headers = {"HTTP_AUTHORIZATION": authorization} if authorization is not None else {}
        # django-stubs gives HttpRequest.__new__ no arguments, which hides DRF Request's constructor.
        return Request(RequestFactory().get("/", **headers))  # pyright: ignore[reportCallIssue]

    def test_platform_key_authenticates_as_a_platform_not_a_person(self):
        """The user is a PlatformClientUser with no staff, superuser or Django permissions."""
        user, client = self.auth.authenticate(self.request(f"Platform {self.key}"))  # type: ignore[misc]
        self.assertEqual(client, self.client_record)
        self.assertIsInstance(user, PlatformClientUser)
        self.assertTrue(user.is_authenticated)
        self.assertFalse(user.is_anonymous)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.has_perm("account.view_account"))
        self.assertEqual(str(user), "platform platform.example.com")

    def test_other_schemes_are_left_to_other_classes(self):
        """No header, or another scheme such as a knox Token, is not this class's to decide."""
        for authorization in (None, "Token abc", "Bearer abc"):
            with self.subTest(authorization):
                self.assertIsNone(self.auth.authenticate(self.request(authorization)))

    def test_bad_platform_keys_are_refused(self):
        """A malformed header or a wrong key raises AuthenticationFailed."""
        for authorization in ("Platform", "Platform a b", "Platform wrong-key"):
            with self.subTest(authorization):
                with self.assertRaises(AuthenticationFailed):
                    self.auth.authenticate(self.request(authorization))

    def test_authenticate_header(self):
        """A 401 names the Platform scheme."""
        self.assertEqual(self.auth.authenticate_header(self.request()), PLATFORM_AUTH_SCHEME)


class TestCreatePlatformApiKeyCommand(AccountTestCase):
    """Test manage.py create_platform_api_key."""

    def run_command(self, *args) -> str:
        """
        Run the command.

        :param args: Its arguments.
        :returns: Its output.
        """
        # pylint: disable=import-outside-toplevel
        from io import StringIO

        out = StringIO()
        call_command("create_platform_api_key", *args, stdout=out)
        return out.getvalue()

    @staticmethod
    def printed_key(output: str) -> str:
        """Return the key from the command's output."""
        line = next(line for line in output.splitlines() if "Platform API key:" in line)
        return line.split("Platform API key:")[1].strip()

    def test_registers_a_platform_and_prints_a_working_key(self):
        """The printed key authenticates the new platform."""
        output = self.run_command("--host", "Alpha.Platform.Example.com", "--description", "alpha")
        client = PlatformClient.objects.get(host_name="alpha.platform.example.com")
        self.assertEqual(client.description, "alpha")
        self.assertEqual(PlatformClient.authenticate(self.printed_key(output)), client)

    def test_refuses_a_second_registration(self):
        """A registered platform is not registered again, and keeps its key."""
        _, key = PlatformClient.create_with_key("alpha.platform.example.com")
        output = self.run_command("--host", "alpha.platform.example.com")
        self.assertNotIn("Platform API key:", output)
        self.assertIsNotNone(PlatformClient.authenticate(key))

    def test_rotate_replaces_the_key(self):
        """--rotate prints a new key, and the old one stops working."""
        client, old_key = PlatformClient.create_with_key("alpha.platform.example.com")
        new_key = self.printed_key(self.run_command("--host", "alpha.platform.example.com", "--rotate"))
        self.assertIsNone(PlatformClient.authenticate(old_key))
        self.assertEqual(PlatformClient.authenticate(new_key), client)

    def test_rotate_needs_a_registered_platform(self):
        """--rotate for an unknown platform creates nothing."""
        output = self.run_command("--host", "unknown.example.com", "--rotate")
        self.assertNotIn("Platform API key:", output)
        self.assertFalse(PlatformClient.objects.exists())
