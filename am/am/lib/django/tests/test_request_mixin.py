"""Test AMRequestMixin."""

from datetime import datetime
from unittest.mock import patch
from urllib.parse import ParseResult

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings

from am.apps.account.tests.mixins import TestAccountMixin
from am.apps.account.utils import get_cached_account_for_user, get_cached_user_profile
from am.common.conf import am_settings
from am.common.exceptions import AMValueError
from am.lib.django.request import AMRequestMixin
from am.lib.drf.models import AMAuthToken


class TestAMRequestMixin(TestAccountMixin):
    """Test AMRequestMixin."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        # the cached lookups are keyed by row id, which an earlier run of the same test database
        # may have cached for other rows: start from fresh ones.
        for user in (self.admin_user, self.non_admin_user):
            get_cached_account_for_user(user, invalidate=True)
            get_cached_user_profile(user, invalidate=True)
            get_cached_user_profile(user, account=self.account, invalidate=True)
        allowed_hosts = override_settings(ALLOWED_HOSTS=["*"])
        allowed_hosts.enable()
        self.addCleanup(allowed_hosts.disable)

    def anonymous(self, path="/", method="get", **kwargs):
        """Return an anonymous request."""
        request = getattr(self.factory, method)(path, **kwargs)
        request.user = AnonymousUser()
        return request

    def test_init_without_request_object(self):
        srm = AMRequestMixin(request=None)
        self.assertIsNone(srm.am_request)
        self.assertFalse(srm.is_requestmixin_ready)
        self.assertFalse(srm.ready)
        self.assertIsNone(srm.data)
        self.assertEqual(srm.unique_client_string, "unique_client_string")
        self.assertIsNone(srm.ip_address)
        self.assertIsNone(srm.user_agent)
        self.assertIsNone(srm.auth_header)
        self.assertIsNone(srm.api_token)
        self.assertIsNone(srm.requester_domain)
        self.assertFalse(srm.qualified_request)
        for prop in ("is_multitenant_domain", "is_environment_root_domain", "is_smarter_api", "is_default_domain"):
            self.assertFalse(getattr(srm, prop), prop)
        for prop in ("path", "root_domain", "subdomain", "domain"):
            self.assertIsNone(getattr(srm, prop), prop)
        self.assertIsInstance(srm.to_json(), dict)
        with self.assertRaises(AttributeError):
            srm.parsed_url  # pylint: disable=pointless-statement

    def test_unauthenticated_base_case(self):
        request = self.anonymous("", SERVER_NAME="testserver")
        srm = AMRequestMixin(request)
        self.assertIsNone(srm.account)
        self.assertIsNone(srm.user)
        self.assertIsInstance(request.user, AnonymousUser, "an anonymous request keeps its AnonymousUser")
        self.assertEqual(srm.domain, "testserver")
        self.assertEqual(srm.ip_address, "127.0.0.1")
        self.assertFalse(srm.is_smarter_api)
        self.assertFalse(srm.is_default_domain)
        self.assertEqual(srm.path, "/")
        self.assertEqual(srm.root_domain, "testserver")
        self.assertEqual(srm.subdomain, "")
        self.assertIsInstance(srm.timestamp, datetime)
        self.assertIsInstance(srm.unique_client_string, str)
        self.assertEqual(srm.url, "http://testserver/")
        self.assertIsInstance(srm.parsed_url, ParseResult)
        self.assertEqual(srm.url_path_parts, [""])
        self.assertEqual(srm.user_agent, "user_agent")
        self.assertTrue(srm.is_requestmixin_ready)
        data = srm.to_json()
        self.assertEqual(data["url"], "http://testserver/")
        self.assertIsNone(data["auth_header"])

    def test_authenticated_request(self):
        request = self.factory.get("/api/v1/accounts/", HTTP_USER_AGENT="test-agent")
        request.user = self.admin_user
        srm = AMRequestMixin(request)
        self.assertEqual(srm.user, self.admin_user)
        self.assertEqual(srm.account, self.account)
        self.assertEqual(srm.user_profile, self.user_profile)
        self.assertTrue(srm.is_authenticated)
        self.assertTrue(srm.ready)
        self.assertTrue(srm.is_smarter_api)
        self.assertEqual(srm.url_path_parts, ["api", "v1", "accounts"])
        self.assertEqual(srm.user_agent, "test-agent")
        self.assertIn(self.account.account_number, srm.unique_client_string)

    def test_api_token_authenticates_the_user(self):
        token_record, token_key = AMAuthToken.objects.create(user=self.admin_user, name=self.name)
        self.addCleanup(token_record.delete)
        request = self.anonymous("/api/v1/accounts/", HTTP_AUTHORIZATION=f"Token {token_key}")
        srm = AMRequestMixin(request)
        self.assertEqual(srm.api_token, token_key.encode())
        self.assertEqual(srm.user, self.admin_user)
        self.assertEqual(request.user, self.admin_user)
        data = srm.to_json()
        self.assertTrue(data["auth_header"].endswith("****"))
        self.assertNotIn(token_key, str(data))

    def test_am_request_can_be_set_later(self):
        srm = AMRequestMixin(None)
        request = self.factory.get("/accounts/")
        request.user = self.non_admin_user
        srm.am_request = request
        self.assertIs(srm.am_request, request)
        self.assertEqual(srm.user, self.non_admin_user)
        self.assertEqual(srm.url, "http://testserver/accounts/")

    def test_invalid_url_raises(self):
        request = self.anonymous("/")
        with patch("am.lib.django.request.smarter_build_absolute_uri", return_value="not-a-url"):
            with self.assertRaises(AMValueError):
                AMRequestMixin(request)
        with patch("am.lib.django.request.smarter_build_absolute_uri", return_value=None):
            with self.assertRaises(AMValueError):
                AMRequestMixin(request)

    def test_url_not_initialized(self):
        srm = AMRequestMixin(self.anonymous("/"))
        srm._url = None  # pylint: disable=protected-access
        with self.assertRaises(AMValueError):
            srm.url  # pylint: disable=pointless-statement
        # deliberately not a ParseResult: a mixin whose url was never parsed
        srm._parse_result = None  # pylint: disable=protected-access  # pyright: ignore[reportAttributeAccessIssue]
        with self.assertRaises(AMValueError):
            srm.url  # pylint: disable=pointless-statement
        with self.assertRaises(AMValueError):
            srm.parsed_url  # pylint: disable=pointless-statement

    def test_is_requestmixin_ready_checks(self):
        srm = AMRequestMixin(None)
        srm._am_request = self.anonymous("/")  # pylint: disable=protected-access
        # deliberately not a ParseResult: a mixin whose url was never parsed
        srm._parse_result = None  # pylint: disable=protected-access  # pyright: ignore[reportAttributeAccessIssue]
        self.assertFalse(srm.is_requestmixin_ready)
        srm = AMRequestMixin(self.anonymous("/"))
        srm._url = None  # pylint: disable=protected-access
        self.assertFalse(AMRequestMixin.is_requestmixin_ready.func(srm))

    def test_json_body(self):
        request = self.anonymous("/accounts/", method="post", data={"a": 1}, content_type="application/json")
        self.assertEqual(AMRequestMixin(request).data, {"a": 1})

    def test_yaml_body(self):
        request = self.anonymous("/accounts/", method="post", data="a: 1\nb: two\n", content_type="application/x-yaml")
        srm = AMRequestMixin(request)
        self.assertEqual(srm.data, {"a": 1, "b": "two"})
        self.assertEqual(srm.data, {"a": 1, "b": "two"})

    def test_unparsable_body(self):
        request = self.anonymous("/accounts/", method="post", data="a: [unclosed", content_type="text/plain")
        with patch("am.lib.django.request.logger") as mock_logger:
            self.assertEqual(AMRequestMixin(request).data, {})
        self.assertNotIn("unclosed", str(mock_logger.error.call_args))

    def test_empty_body(self):
        self.assertEqual(AMRequestMixin(self.anonymous("/accounts/")).data, {})

    def test_unqualified_requests_have_no_data(self):
        for path in ["/admin/foo/", "/docs/foo/", "/static/app.js", "/favicon.ico"]:
            with self.subTest(path=path):
                srm = AMRequestMixin(self.anonymous(path))
                self.assertFalse(srm.qualified_request)
                self.assertIsNone(srm.data)

    def test_internal_host_is_not_qualified(self):
        srm = AMRequestMixin(self.anonymous("/accounts/", HTTP_HOST="192.168.1.10"))
        self.assertFalse(srm.qualified_request)

    def test_amnesty_url_is_not_qualified(self):
        srm = AMRequestMixin(self.anonymous("/"))
        srm._parse_result = srm._parse_result._replace(path="healthz")  # pylint: disable=protected-access
        self.assertFalse(srm.qualified_request)
        srm = AMRequestMixin(self.anonymous("/"))
        srm._parse_result = srm._parse_result._replace(path="")  # pylint: disable=protected-access
        self.assertFalse(srm.qualified_request)

    def test_params(self):
        srm = AMRequestMixin(self.anonymous("/accounts/", data={"uid": "xyz"}))
        self.assertEqual(srm.params.get("uid"), "xyz")
        srm = AMRequestMixin(None)
        self.assertIsNone(srm.params)

    def test_requester_domain(self):
        srm = AMRequestMixin(self.anonymous("/", HTTP_X_FORWARDED_FOR="93.184.216.34"))
        with patch("am.lib.django.request.socket.gethostbyaddr", return_value=("example.com", [], [])) as lookup:
            self.assertEqual(srm.requester_domain, "example.com")
            self.assertEqual(srm.requester_domain, "example.com")
        lookup.assert_called_once_with("93.184.216.34")

    def test_requester_domain_falls_back_to_ip(self):
        srm = AMRequestMixin(self.anonymous("/"))
        with patch("am.lib.django.request.socket.gethostbyaddr", side_effect=OSError("no PTR record")):
            self.assertEqual(srm.requester_domain, "127.0.0.1")

    def test_requester_domain_setter_and_multitenant(self):
        srm = AMRequestMixin(self.anonymous("/"))
        srm.requester_domain = am_settings.platform_domain
        self.assertEqual(srm.requester_domain, am_settings.platform_domain)
        self.assertTrue(srm.is_multitenant_domain)
        srm = AMRequestMixin(self.anonymous("/"))
        srm.requester_domain = "other.example.com"
        self.assertFalse(srm.is_multitenant_domain)

    def test_environment_root_domain(self):
        request = self.anonymous("/", HTTP_HOST=am_settings.environment_domain)
        srm = AMRequestMixin(request)
        self.assertTrue(srm.is_environment_root_domain)
        self.assertFalse(AMRequestMixin(self.anonymous("/accounts/")).is_environment_root_domain)

    def test_default_domain_and_root_domain(self):
        request = self.anonymous("/accounts/", HTTP_HOST=am_settings.environment_api_domain)
        srm = AMRequestMixin(request)
        self.assertTrue(srm.is_default_domain)
        self.assertIsNotNone(srm.root_domain)
        srm = AMRequestMixin(self.anonymous("/accounts/", HTTP_HOST="api.example.com"))
        self.assertEqual(srm.root_domain, "example.com")
        self.assertEqual(srm.subdomain, "api")
        self.assertEqual(srm.domain, "api.example.com")

    def test_formatted_class_name(self):
        self.assertTrue(AMRequestMixin(None).formatted_class_name.endswith("AMRequestMixin()"))
