"""Test the AMValidator class."""

from am.common.const import ACCOUNT_API_SUBDOMAIN
from am.common.exceptions import AMValueError
from am.lib.unittest.base_classes import AMTestBase

from ..validators import AMValidator


class TestAMValidator(AMTestBase):
    """Test the AMValidator class."""

    def test_validate_account_number(self):
        self.assertEqual(AMValidator.validate_account_number("1234-5678-9012"), "1234-5678-9012")
        with self.assertRaises(AMValueError):
            AMValidator.validate_account_number("1234-5678-901")

    def test_validate_domain(self):
        self.assertEqual(AMValidator.validate_domain("example.com"), "example.com")
        self.assertEqual(AMValidator.validate_domain("api.example.com:8443"), "api.example.com:8443")
        self.assertEqual(AMValidator.validate_domain("localhost:8000"), "localhost:8000")
        self.assertIsNone(AMValidator.validate_domain(None))
        self.assertEqual(AMValidator.validate_domain(""), "")
        with self.assertRaises(AMValueError):
            AMValidator.validate_domain("invalid domain")

    def test_validate_email(self):
        self.assertEqual(AMValidator.validate_email("user@example.com"), "user@example.com")
        with self.assertRaises(AMValueError):
            AMValidator.validate_email("invalid-email")

    def test_is_valid_email(self):
        self.assertTrue(AMValidator.is_valid_email("user@example.com"))
        self.assertFalse(AMValidator.is_valid_email("invalid-email"))

    def test_validate_ip(self):
        self.assertEqual(AMValidator.validate_ip("192.168.1.1"), "192.168.1.1")
        with self.assertRaises(AMValueError):
            AMValidator.validate_ip("999.999.999.999")

    def test_is_valid_ip(self):
        self.assertTrue(AMValidator.is_valid_ip("10.0.0.1"))
        self.assertFalse(AMValidator.is_valid_ip("not-an-ip"))

    def test_validate_url(self):
        for url in [
            "https://example.com",
            "https://example.com:8443/path/?q=1",
            "http://localhost:8000/api/",
            "http://testserver/",
            "http://intranet",  # no top-level domain: accepted, it has a host
        ]:
            with self.subTest(url=url):
                self.assertEqual(AMValidator.validate_url(url), url)

    def test_validate_url_rejects(self):
        for url in ["", None, 42, "ftp://example.com", "example.com", "http://"]:
            with self.subTest(url=url), self.assertRaises(AMValueError):
                AMValidator.validate_url(url)  # type: ignore[arg-type]

    def test_is_valid_url(self):
        self.assertTrue(AMValidator.is_valid_url("https://example.com"))
        self.assertFalse(AMValidator.is_valid_url("invalid_url"))

    def test_validate_hostname(self):
        self.assertEqual(AMValidator.validate_hostname("example.com"), "example.com")
        self.assertEqual(AMValidator.validate_hostname("example.com."), "example.com")
        self.assertEqual(AMValidator.validate_hostname("example.com:8000"), "example.com")
        for hostname in ["invalid_hostname!", "example.com:99999", "example.com:port", "a" * 256, "-bad.com"]:
            with self.subTest(hostname=hostname), self.assertRaises(AMValueError):
                AMValidator.validate_hostname(hostname)

    def test_is_valid_hostname(self):
        self.assertTrue(AMValidator.is_valid_hostname("example.com"))
        self.assertFalse(AMValidator.is_valid_hostname("invalid_hostname!"))

    def test_is_api_endpoint(self):
        self.assertTrue(AMValidator.is_api_endpoint("https://example.com/api/v1/accounts/"))
        self.assertTrue(AMValidator.is_api_endpoint(f"https://{ACCOUNT_API_SUBDOMAIN}.example.com/accounts/"))
        self.assertFalse(AMValidator.is_api_endpoint("https://example.com/accounts/"))
        self.assertFalse(AMValidator.is_api_endpoint("not a url"))
        self.assertFalse(AMValidator.is_api_endpoint(None))  # type: ignore[arg-type]

    def test_base_url(self):
        self.assertEqual(AMValidator.base_url("https://example.com/path/?q=1"), "https://example.com/")
        self.assertIsNone(AMValidator.base_url(""))
        with self.assertRaises(AMValueError):
            AMValidator.base_url("example.com")

    def test_trailing_slash(self):
        self.assertEqual(AMValidator.trailing_slash("https://example.com"), "https://example.com/")
        self.assertEqual(AMValidator.trailing_slash("https://example.com/"), "https://example.com/")
        self.assertIsNone(AMValidator.trailing_slash(""))

    def test_urlify(self):
        self.assertEqual(AMValidator.urlify("example.com"), "http://example.com/")
        self.assertEqual(AMValidator.urlify("example.com", environment="prod"), "https://example.com/")
        self.assertEqual(AMValidator.urlify("https://example.com/path"), "https://example.com/path/")
        with self.assertRaises(AMValueError):
            AMValidator.urlify("")
        with self.assertRaises(AMValueError):
            AMValidator.urlify("ftp://example.com")
