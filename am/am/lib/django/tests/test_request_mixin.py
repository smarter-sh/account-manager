"""Test AMRequestMixin."""

from datetime import datetime
from logging import getLogger
from urllib.parse import ParseResult

from django.contrib.auth import authenticate
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory

from am.apps.account.tests.mixins import TestAccountMixin
from am.apps.account.utils import get_cached_smarter_admin_user_profile
from am.common.utils import is_authenticated_request
from am.lib.django.request import AMRequestMixin


ACCOUNT_DEV_ADMIN_PASSWORD = "account"
logger = getLogger(__name__)


class TestAMRequestMixin(TestAccountMixin):
    """
    Test AMRequestMixin.
    example urls:
    - http://testserver
    - http://localhost:8000/
    - http://localhost:8000/docs/
    - http://localhost:8000/dashboard/
    - https://alpha.account.smarter.sh/api/v1/workbench/1/chatbot/
    - https://alpha.account.smarter.sh/api/v1/cli/chat/example/
    - http://example.com/contact/
    - https://hr.3141-5926-5359.alpha.api.smarter.sh/
    - http://example.3141-5926-5359.api.localhost:8000/
    - http://localhost:8000/api/v1/workbench/1/chat/
    - https://hr.smarter.sh/

    """

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.wsgi_request_factory = RequestFactory()

    def tearDown(self):
        try:
            self.client.logout()
            self.client = None
            self.wsgi_request_factory = None
        # pylint: disable=W0718
        except Exception:
            pass

    def get_smarter_request_mixin(self, url: str) -> AMRequestMixin:
        request_factory = RequestFactory()
        request = request_factory.get(url, SERVER_NAME="localhost:8000")
        smarter_admin_user_profile = get_cached_smarter_admin_user_profile()
        user = authenticate(username=smarter_admin_user_profile.user.username, password=ACCOUNT_DEV_ADMIN_PASSWORD)
        if user is None:
            self.fail("Authentication failed")
        request.user = user
        middleware = SessionMiddleware(lambda request: None)
        middleware.process_request(request)
        request.session.save()

        return AMRequestMixin(request)

    def test_init_without_request_object(self):
        """
        Test that AMRequestMixin will initialize without a request object.
        """
        AMRequestMixin(request=None)

    def test_unauthenticated_instantiation(self):
        """
        Test that AMRequestMixin can be instantiated with an unauthenticated request.
        """
        request = self.wsgi_request_factory.get("/")

        srm = AMRequestMixin(request)
        self.assertIsNotNone(srm.to_json())

    def test_authenticated_instantiation(self):
        """
        Test that AMRequestMixin can be instantiated with an authenticated request.
        """
        self.client.login(username=self.admin_user.username, password="12345")
        response = self.client.get("/")
        request = response.wsgi_request

        srm = AMRequestMixin(request)
        self.assertIsNotNone(srm.to_json())

    def test_request_object_can_be_set(self):
        """
        Test that AMRequestMixin request object is read-only.
        """
        self.client.login(username=self.admin_user.username, password="12345")
        response = self.client.get("/")

        # we should be able to instantiate AMRequestMixin with a None request
        request = None
        srm = AMRequestMixin(request)

        # and afterwards we should later be able to set am_request
        srm.am_request = response.wsgi_request

        # and after that, we should see authenticated user data
        self.assertIsNotNone(srm.user)
        self.assertIsNotNone(srm.account)
        self.assertIsNotNone(srm.user_profile)
        self.assertIsNotNone(srm.url)
        self.assertTrue(srm.is_authenticated)

    def test_unauthenticated_base_case(self):
        """
        Test that AMRequestMixin can be instantiated with an unauthenticated request.
        """
        request = self.wsgi_request_factory.get("", SERVER_NAME="testserver")
        srm = AMRequestMixin(request)
        self.assertIsNone(srm.account)
        self.assertEqual(srm.domain, "testserver")
        self.assertEqual(srm.ip_address, "127.0.0.1")
        self.assertFalse(srm.is_smarter_api)
        self.assertFalse(srm.is_default_domain)
        self.assertEqual(srm.path, "/")
        self.assertEqual(srm.root_domain, "testserver")
        self.assertEqual(srm.subdomain, "")
        self.assertIsNone(srm.user)
        self.assertIsInstance(srm.timestamp, datetime)
        try:
            dt = datetime.fromisoformat(str(srm.timestamp))
            self.assertIsInstance(dt, datetime)
        except ValueError:
            self.fail("The timestamp could not be converted to a datetime object")

        self.assertIsNotNone(srm.unique_client_string)
        self.assertIsInstance(srm.unique_client_string, str)
        self.assertIsNotNone(srm.url)
        self.assertIsInstance(srm.url, str)
        self.assertEqual(srm.url, "http://testserver/")
        self.assertIsInstance(srm.parsed_url, ParseResult)
        self.assertIsNotNone(srm.to_json())
        self.assertIsInstance(srm.to_json(), dict)

    def test_named_api_url(self):
        """
        Test that AMRequestMixin can be instantiated with an unauthenticated request.
        http://example.3141-5926-5359.api.localhost:8000/

        we need to authenticate with the Smarter admin account and the dev environment
        needs to be fully initialized.
        """
        url = "http://example.3141-5926-5359.api.localhost:8000/"
        smarter_admin_user_profile = get_cached_smarter_admin_user_profile()
        if smarter_admin_user_profile is None:
            self.skipTest("Smarter admin user profile is not available")

        self.client.login(username=smarter_admin_user_profile.user.username, password=ACCOUNT_DEV_ADMIN_PASSWORD)
        response = self.client.get(url, SERVER_NAME="example.3141-5926-5359.api.localhost:8000")
        request = response.wsgi_request
        self.assertEqual(request.user, smarter_admin_user_profile.user)
        self.assertEqual(url, request.build_absolute_uri())
        if not is_authenticated_request(request):
            self.skipTest("User is not authenticated")

        srm = AMRequestMixin(request)

        self.assertEqual(srm.account, smarter_admin_user_profile.account)
        self.assertEqual(srm.user, smarter_admin_user_profile.user)
        self.assertEqual(srm.url, url)
        self.assertFalse(srm.is_smarter_api)
        self.assertEqual(srm.domain, "example.3141-5926-5359.api.localhost:8000")
