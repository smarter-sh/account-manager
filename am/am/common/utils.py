# pylint: disable=duplicate-code
# pylint: disable=E1101
"""
Utility functions for the Account Manager application.

This module provides a collection of helper functions and classes
that are ostensibly implemented in more than one Account Manager base class.
Hence, they are only here in order to keep the code DRY (Don't Repeat Yourself).

The module is intended for internal use within the Account Manager application and is
designed to be compatible with Python 3, Django, DRF, and Pydantic.
"""

import hashlib
import logging
import random
import re
import warnings
from typing import Optional, Union

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpRequest
from rest_framework.request import Request

from am.common.exceptions import AMValueError
from am.common.helpers.console_helpers import formatted_text
from am.lib.django.validators import AMValidator

RequestType = Union[HttpRequest, Request, WSGIRequest]
logger = logging.getLogger(__name__)


def is_authenticated_request(request: Optional[RequestType]) -> bool:
    """
    Determines whether the provided request is authenticated.

    :param request: The request object to check. This can be an instance of :class:`django.http.HttpRequest`, :class:`rest_framework.request.Request`, or :class:`django.core.handlers.wsgi.WSGIRequest`. If ``None`` is provided, the function will return ``False``.

    :type request: Optional[Union[HttpRequest, Request, WSGIRequest]]

    :return: Returns ``True`` if the request is authenticated (i.e., the request has a ``user`` attribute and ``user.is_authenticated`` is ``True``). Returns ``False`` otherwise.
    :rtype: bool

    :raises Exception: Any unexpected error during attribute access will be caught and logged; the function will return ``False`` in such cases.

    .. note::
        This function is compatible with Django and Django REST Framework request objects. It also supports WSGIRequest and can be used in unit tests with mock objects that have the required attributes.

    .. warning::
        If the request object does not have a ``user`` attribute, or if ``user.is_authenticated`` is not available, the function will return ``False``. Any exceptions are logged as warnings.

    **Example usage:**

    .. code-block:: python

        from am.common.utils import is_authenticated_request
        from django.http import HttpRequest

        request = HttpRequest()
        request.user = SomeUserObject()
        authenticated = is_authenticated_request(request)
        print(authenticated)  # True or False depending on user.is_authenticated

    .. code-block:: python

        # Example with DRF Request
        from rest_framework.request import Request

        drf_request = Request(...)
        authenticated = is_authenticated_request(drf_request)
        print(authenticated)
    """
    try:
        return (
            isinstance(request, (HttpRequest, Request, WSGIRequest))
            and hasattr(request, "user")
            and hasattr(request.user, "is_authenticated")
            and request.user.is_authenticated
        )
    # pylint: disable=W0718
    except Exception as e:
        logger.warning("is_authenticated_request() failed: %s", formatted_text(str(e)))
        return False


def hash_factory(length: int = 16) -> str:
    """
    Generates a random hexadecimal hash string of the specified length.

    :param length: The desired length of the hash string. Must be a positive integer. If the value exceeds the length of a SHA-256 hash (64), the result will be truncated to the maximum available length.
    :type length: int, optional (default is 16)

    :return: A random hexadecimal string of the specified length.
    :rtype: str

    .. note::
        The hash is generated using a random 256-bit integer, encoded with SHA-256, and truncated to the requested length. The output is suitable for use as a unique identifier, token, or nonce in most application contexts.

    .. warning::
        This function does not guarantee cryptographic security for all use cases. For security-critical applications (such as password hashing or cryptographic keys), use dedicated libraries and algorithms.

    **Example usage:**

    .. code-block:: python

        from am.common.utils import hash_factory

        # Generate a 16-character random hash
        token = hash_factory()
        print(token)  # e.g., 'a3f9c1e2b4d5f6a7'

        # Generate a 32-character random hash
        long_token = hash_factory(length=32)
        print(long_token)  # e.g., 'a3f9c1e2b4d5f6a7c8e9d0b1a2c3d4e5'
    """
    return hashlib.sha256(str(random.getrandbits(256)).encode("utf-8")).hexdigest()[:length]


def mask_string(string: str, mask_char: str = "*", mask_length: int = 4, string_length: int = 8) -> str:
    """
    Masks a string by replacing all but the last ``mask_length`` characters with ``mask_char``.

    .. deprecated:: 0.10.0
        This function is deprecated and will be removed in a future release.
        Use Pydantic's ``SecretStr`` or other secure alternatives for string masking.

    :param string: The string to mask. If a ``bytes`` object is provided, it will be decoded to UTF-8.
    :type string: str or bytes

    :param mask_char: The character to use for masking. Default is ``'*'``.
    :type mask_char: str, optional

    :param mask_length: The number of characters at the end of the string to leave unmasked. Must be non-negative and less than or equal to the length of the string.
    :type mask_length: int, optional

    :param string_length: The total length of the returned masked string. If the original string is shorter, the result will be truncated or padded accordingly.
    :type string_length: int, optional

    :return: The masked string, with all but the last ``mask_length`` characters replaced by ``mask_char``. The result is truncated to ``string_length`` if necessary.
    :rtype: str

    :raises TypeError: If ``string`` is not a string or bytes.
    :raises ValueError: If ``mask_length`` or ``string_length`` are negative, or if ``mask_length`` exceeds the length of the string.

    .. note::

        - If the input string is shorter than ``mask_length``, the original string is returned.
        - If ``mask_length`` is greater than ``string_length``, it is reduced to ``string_length``.

    **Example usage:**

    .. code-block:: python

        from am.common.utils import mask_string

        # Mask all but the last 4 characters
        masked = mask_string("supersecretpassword", mask_char="*", mask_length=4)
        print(masked)  # Output: ****word

        # Mask and truncate to 8 characters
        masked = mask_string("supersecretpassword", mask_char="#", mask_length=3, string_length=8)
        print(masked)  # Output: #####ord

        # Mask a short string
        masked = mask_string("abc", mask_length=4)
        print(masked)  # Output: abc
    """
    warnings.warn(
        "mask_string is deprecated and will be removed in a future release.", DeprecationWarning, stacklevel=2
    )
    if isinstance(string, bytes):
        string = string.decode("utf-8")
    if not isinstance(string, str):
        raise TypeError("string must be a string")
    if len(string) <= mask_length:
        return string
    if mask_length < 0:
        raise ValueError("mask_length must be greater than or equal to 0")
    if string_length < 0:
        raise ValueError("string_length must be greater than or equal to 0")
    if string_length > len(string):
        string_length = len(string)
    if mask_length > string_length:
        mask_length = string_length

    # slice with explicit start indexes: string[-0:] would be the whole string, unmasked
    masked_string = f"{mask_char * (len(string) - mask_length)}{string[len(string) - mask_length:]}"
    return masked_string[len(masked_string) - string_length :]


def smarter_build_absolute_uri(request: Optional[Union[HttpRequest, Request]]) -> Optional[str]:
    """
    Attempts to construct the absolute URI for a given request object.

    :param request: The request object, which may be an instance of :class:`django.http.HttpRequest`, :class:`rest_framework.request.Request`, :class:`django.core.handlers.wsgi.WSGIRequest`, or a mock object for testing.
    :type request: HttpRequest or compatible type

    :return: The absolute URI as a string, or a fallback test URL if the request is invalid or cannot be resolved.
    :rtype: Optional[str]

    .. note::
        - If the request is a Django REST Framework ``Request``, it is recast to a Django ``HttpRequest``.
        - If the request is a mock object (e.g., from unit tests), a synthetic test URL is returned.
        - The function first tries to use Django's ``build_absolute_uri`` method. If unavailable, it attempts to build the URL from scheme, host, and path attributes.
        - If all attempts fail, a generic fallback URL is returned.

    .. warning::
        If the request is ``None`` or cannot be resolved, the function logs a warning and returns a fallback test URL. Always validate the returned URL before using it in production.

    **Example usage:**

    .. code-block:: python

        from am.common.utils import smarter_build_absolute_uri
        from django.http import HttpRequest

        request = HttpRequest()
        request.META['HTTP_HOST'] = 'localhost:8000'
        request.path = '/api/v1/resource/'
        url = smarter_build_absolute_uri(request)
        print(url)  # Output: http://localhost:8000/api/v1/resource/

        # Example with DRF Request
        from rest_framework.request import Request
        drf_request = Request(...)
        url = smarter_build_absolute_uri(drf_request)
        print(url)

        # Example with None
        url = smarter_build_absolute_uri(None)
        print(url)  # Output: http://testserver/unknown/
    """
    if request is None:
        logger.warning("smarter_build_absolute_uri() called with None request")
        return "http://testserver/unknown/"

    if isinstance(request, Request):
        # recast DRF Request to Django HttpRequest
        # pylint: disable=W0212
        request = request._request

    # If it's a unittest.mock.Mock, synthesize a fake URL for testing
    if hasattr(request, "__class__") and request.__class__.__name__ == "Mock":
        logger.info("smarter_build_absolute_uri() called with Mock request; returning fake test URL")
        return "http://testserver/mockpath/"

    # Try to use Django's build_absolute_uri if available
    if hasattr(request, "build_absolute_uri"):
        try:
            url = request.build_absolute_uri()
            if url:
                return url
        # pylint: disable=W0718
        except Exception as e:
            logger.warning(
                "smarter_build_absolute_uri() failed to call request.build_absolute_uri(): %s",
                formatted_text(str(e)),
            )

    # Try to build from scheme, host, and path
    try:
        scheme = getattr(request, "scheme", None) or getattr(request, "META", {}).get("wsgi.url_scheme", "http")
        host = (
            getattr(request, "get_host", lambda: None)()
            or getattr(request, "META", {}).get("HTTP_HOST")
            or getattr(request, "META", {}).get("SERVER_NAME")
            or "testserver"
        )
        path = getattr(request, "get_full_path", lambda: None)() or "/"
        url = f"{scheme}://{host}{path}"
        if AMValidator.is_valid_url(url):
            return url
    # pylint: disable=W0718
    except Exception as e:
        logger.warning(
            "smarter_build_absolute_uri() failed to build URL from request attributes: %s",
            formatted_text(str(e)),
        )

    # Fallback: synthesize a generic test URL
    logger.warning("smarter_build_absolute_uri() could not determine URL, returning fallback test URL")
    return "http://testserver/unknown/"


def camel_to_snake(data: Union[str, dict, list]) -> Optional[Union[str, dict, list]]:
    """
    Converts camelCase strings, dictionary keys, or lists of such, to snake_case format.

    :param data: The input to convert. Can be a string, a dictionary (with camelCase keys), or a list containing strings or dictionaries.
    :type data: str, dict, or list

    :return: The converted data in snake_case format. Returns a string, dictionary, or list, matching the input type.
    :rtype: Optional[Union[str, dict, list]]

    .. note::
        - For dictionaries, only keys are converted. Values are preserved as-is, except for nested dictionaries, which are also converted.
        - Spaces in keys are replaced with underscores.
        - Multiple consecutive underscores are collapsed into a single underscore.
        - Nested dictionaries and lists are processed recursively.

    .. warning::
        If the input is not a string, dictionary, or list, a ``AMValueError`` is raised.

    **Example usage:**

    .. code-block:: python

        from am.common.utils import camel_to_snake

        # Convert a string
        print(camel_to_snake("userName"))  # Output: user_name

        # Convert a dictionary
        data = {
            "userName": "alice",
            "userProfile": {
                "firstName": "Alice",
                "lastName": "Smith"
            }
        }
        print(camel_to_snake(data))
        # Output: {'user_name': 'alice', 'user_profile': {'first_name': 'Alice', 'last_name': 'Smith'}}

        # Convert a list of strings
        print(camel_to_snake(["firstName", "lastName"]))
        # Output: ['first_name', 'last_name']
    """

    def convert(name: str):
        name = name.replace(" ", "_")
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        result = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        result = re.sub("_+", "_", result)
        return result

    if isinstance(data, str):
        return convert(data)
    if isinstance(data, list):
        return [camel_to_snake(item) for item in data]
    if not isinstance(data, dict):
        raise AMValueError(f"Expected data to be a dict or list, got: {type(data)}")
    dictionary: dict = data if isinstance(data, dict) else {}
    retval = {}
    for key, value in dictionary.items():
        if isinstance(value, dict):
            value = camel_to_snake(value)
        new_key = convert(key)
        retval[new_key] = value
    return retval
