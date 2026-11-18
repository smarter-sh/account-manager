"""Unit test class."""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from am.common.helpers.email_helpers import EmailHelper
from am.lib.unittest.base_classes import AMTestBase

from .factories import admin_user_factory, factory_account_teardown, mortal_user_factory

LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "am-account-tests",
    }
}
"""
A per-process cache for tests that use Django's transaction rollback.

The
shared Redis cache would otherwise hand later tests (and concurrent test runs)
model instances whose rows were rolled back.
"""


class TestAccountMixin(AMTestBase):
    """A mixin that adds class-level account and user creation/destruction."""

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class with a single account, and admin and non-admin users.

        using the class setup so that we retain the same user_profile for each test.

        Every new AccountContact is sent a welcome email, so SMTP is patched for the
        lifetime of the class: no test reaches the real mail server.
        """
        cls._smtp_patchers = [
            mock.patch("am.common.helpers.email_helpers.smtplib.SMTP"),
            mock.patch("am.common.helpers.email_helpers.smtplib.SMTP_SSL"),
        ]
        for patcher in cls._smtp_patchers:
            patcher.start()
        super().setUpClass()
        cls.admin_user, cls.account, cls.user_profile = admin_user_factory()
        cls.non_admin_user, _, cls.non_admin_user_profile = mortal_user_factory(account=cls.account)

    @classmethod
    def tearDownClass(cls):
        try:
            factory_account_teardown(user=cls.admin_user, account=None, user_profile=cls.user_profile)
            factory_account_teardown(
                user=cls.non_admin_user, account=cls.account, user_profile=cls.non_admin_user_profile
            )
        # pylint: disable=W0718
        except Exception:
            pass
        finally:
            super().tearDownClass()
            for patcher in cls._smtp_patchers:
                patcher.stop()

    def setUp(self):
        """We use different manifest test data depending on the test case."""
        super().setUp()
        self._manifest = None
        self._manifest_path = None
        self._loader = None
        self._model = None

    def tearDown(self):
        """We use different manifest test data depending on the test case."""
        self._manifest = None
        self._manifest_path = None
        self._loader = None
        self._model = None
        super().tearDown()


@override_settings(CACHES=LOCMEM_CACHES)
class AccountTestCase(TestCase):
    """
    Django ``TestCase`` (transaction rollback) for the account app.

    - The cache is a per-process LocMemCache, cleared before every test.
    - :meth:`EmailHelper.send_email` is patched for the lifetime of the class;
      ``self.send_email`` is the mock, reset before every test, so tests can
      assert on the emails that would have been sent.
    """

    send_email: mock.MagicMock

    @classmethod
    def setUpClass(cls):
        cls._send_email_patcher = mock.patch.object(EmailHelper, "send_email")
        cls.send_email = cls._send_email_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._send_email_patcher.stop()

    def setUp(self):
        super().setUp()
        cache.clear()
        self.send_email.reset_mock()
