"""Test am.common.utils."""

import warnings
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from django.http import HttpRequest
from django.test import RequestFactory
from rest_framework.request import Request

from am.common.exceptions import AMValueError
from am.common.utils import (
    camel_to_snake,
    hash_factory,
    is_authenticated_request,
    mask_string,
    smarter_build_absolute_uri,
)
from am.lib.unittest.base_classes import AMTestBase


def masked(*args, **kwargs) -> str:
    """Call the deprecated mask_string() without its deprecation warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return mask_string(*args, **kwargs)


class TestUtils(AMTestBase):
    """Test am.common.utils."""

    def test_is_authenticated_request(self):
        """Only a request whose user is authenticated is an authenticated request."""
        self.assertFalse(is_authenticated_request(None))
        self.assertFalse(is_authenticated_request(MagicMock()))

        request = RequestFactory().get("/")
        self.assertFalse(is_authenticated_request(request))

        request.user = MagicMock(is_authenticated=True)
        self.assertTrue(is_authenticated_request(request))

        request.user = MagicMock(is_authenticated=False)
        self.assertFalse(is_authenticated_request(request))

    def test_is_authenticated_request_error(self):
        """An error while reading the user is logged, and the request is not authenticated."""
        request = RequestFactory().get("/")
        user = MagicMock()
        type(user).is_authenticated = PropertyMock(side_effect=RuntimeError("boom"))
        request.user = user
        self.assertFalse(is_authenticated_request(request))

    def test_hash_factory(self):
        """Hash_factory() returns random hex strings of the requested length."""
        value = hash_factory()
        self.assertEqual(len(value), 16)
        int(value, 16)
        self.assertEqual(len(hash_factory(length=32)), 32)
        self.assertEqual(len(hash_factory(length=100)), 64)
        self.assertNotEqual(hash_factory(), hash_factory())

    def test_mask_string(self):
        """Mask_string() shows only the last characters, within the requested length."""
        self.assertEqual(masked("supersecretpassword"), "****word")
        self.assertEqual(masked("supersecretpassword", mask_char="#", mask_length=3, string_length=8), "#####ord")
        self.assertEqual(masked("supersecret", mask_length=2, string_length=30), "*********et")
        self.assertEqual(masked(b"supersecretpassword"), "****word")
        self.assertEqual(masked("abc", mask_length=4), "abc")

    def test_mask_string_never_reveals_the_string(self):
        """A mask_length or string_length of 0 masks everything."""
        self.assertEqual(masked("secret", mask_length=0), "******")
        self.assertEqual(masked("secretvalue", mask_length=4, string_length=0), "")
        self.assertEqual(masked("secretvalue", mask_length=6, string_length=4), "alue")

    def test_mask_string_errors(self):
        """Mask_string() refuses non-strings and negative lengths, and is deprecated."""
        with self.assertRaises(TypeError):
            masked(12345)
        with self.assertRaises(ValueError):
            masked("secret", mask_length=-1)
        with self.assertRaises(ValueError):
            masked("secret", string_length=-1)
        with self.assertWarns(DeprecationWarning):
            mask_string("secret")

    def test_smarter_build_absolute_uri(self):
        """Django and DRF requests give their absolute uri."""
        request = RequestFactory().get("/api/v1/resource/?a=1")
        self.assertEqual(smarter_build_absolute_uri(request), "http://testserver/api/v1/resource/?a=1")
        # django-stubs types HttpRequest.__new__ without arguments, which hides DRF's Request.__init__.
        drf_request = Request(request)  # pyright: ignore[reportCallIssue]
        self.assertEqual(smarter_build_absolute_uri(drf_request), "http://testserver/api/v1/resource/?a=1")

    def test_smarter_build_absolute_uri_fallbacks(self):
        """None and Mock requests give synthetic test urls."""
        self.assertEqual(smarter_build_absolute_uri(None), "http://testserver/unknown/")
        self.assertEqual(smarter_build_absolute_uri(Mock()), "http://testserver/mockpath/")

    def test_smarter_build_absolute_uri_from_attributes(self):
        """When build_absolute_uri() fails, the url is built from the request's attributes."""
        request = HttpRequest()
        request.META = {"HTTP_HOST": "testserver", "SERVER_PORT": "80"}
        request.path = "/path/"
        request.build_absolute_uri = MagicMock(side_effect=RuntimeError("boom"))
        self.assertEqual(smarter_build_absolute_uri(request), "http://testserver/path/")

        request.build_absolute_uri = MagicMock(return_value="")
        self.assertEqual(smarter_build_absolute_uri(request), "http://testserver/path/")

    def test_smarter_build_absolute_uri_from_plain_object(self):
        """An object without request methods falls back to META, then to a test url."""

        class Plain:
            """A request-like object."""

            META = {"SERVER_NAME": "example.com", "wsgi.url_scheme": "https"}

        # Plain and Broken are deliberately not requests.
        plain = Plain()
        url = smarter_build_absolute_uri(plain)  # pyright: ignore[reportArgumentType]
        self.assertEqual(url, "https://example.com/")

        with patch("am.common.utils.AMValidator.is_valid_url", return_value=False):
            url = smarter_build_absolute_uri(plain)  # pyright: ignore[reportArgumentType]
            self.assertEqual(url, "http://testserver/unknown/")

        class Broken:
            """A request-like object that raises."""

            @property
            def scheme(self):
                raise RuntimeError("boom")

        url = smarter_build_absolute_uri(Broken())  # pyright: ignore[reportArgumentType]
        self.assertEqual(url, "http://testserver/unknown/")

    def test_camel_to_snake(self):
        """Camel_to_snake() converts strings, lists and dict keys."""
        self.assertEqual(camel_to_snake("camelCase"), "camel_case")
        self.assertEqual(camel_to_snake("CamelCase"), "camel_case")
        self.assertEqual(camel_to_snake("Camel Case"), "camel_case")
        self.assertEqual(camel_to_snake("MYEverlastingSUPERDUPERGobstopper"), "my_everlasting_superduper_gobstopper")
        self.assertEqual(camel_to_snake("already_snake_case"), "already_snake_case")
        self.assertEqual(camel_to_snake(""), "")
        self.assertEqual(camel_to_snake(["firstName", "lastName"]), ["first_name", "last_name"])
        self.assertEqual(
            camel_to_snake({"userName": "aliceSmith", "userProfile": {"firstName": "Alice"}}),
            {"user_name": "aliceSmith", "user_profile": {"first_name": "Alice"}},
        )

    def test_camel_to_snake_invalid(self):
        """Camel_to_snake() refuses other types."""
        with self.assertRaises(AMValueError):
            camel_to_snake(42)  # type: ignore[arg-type]
