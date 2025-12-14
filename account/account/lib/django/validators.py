# pylint: disable=C0413,C0302
"""
Internal validation features. This module contains functions for validating various data types.
Before adding anything to this module, please first check if there is a built-in Python function
or a Django utility that can do the validation.

"""

import logging


logger = logging.getLogger(__name__)

import re
import warnings
from typing import Optional
from urllib.parse import urlparse, urlunparse

import validators


try:
    from django.core.exceptions import ValidationError  # type: ignore
except ImportError:
    logger.warning("Django is not installed. Some validation features may not work.")

    # pylint: disable=missing-class-docstring
    class ValidationError(Exception):
        pass


try:
    from django.core.validators import URLValidator  # type: ignore
    from django.core.validators import (
        validate_email,
        validate_ipv4_address,
    )
except ImportError:
    logger.warning("Django is not installed. Some validation features may not work.")

    # pylint: disable=missing-function-docstring,unused-argument

    # pylint: disable=missing-class-docstring
    class URLValidator:
        def __init__(self, *args, **kwargs):
            logger.warning("Django is not installed. URLValidator will not function properly.")

        def __call__(self, value):
            # Optionally, you could raise NotImplementedError or just pass
            logger.warning("Django is not installed. URLValidator will not function properly.")

    # pylint: disable=missing-function-docstring,unused-argument
    def validate_email(*args, **kwargs):
        logger.warning("Django is not installed. validate_email will not function properly.")

    # pylint: disable=missing-function-docstring,unused-argument
    def validate_ipv4_address(*args, **kwargs):
        logger.warning("Django is not installed. validate_ipv4_address will not function properly.")


from account.common.const import ACCOUNT_API_SUBDOMAIN, AMEnvironments
from account.common.exceptions import AMValueError
from account.lib import json


# pylint: disable=R0904
class AMValidator:
    """
    Class for validating various data types. Before adding anything to this class, please
    first check if there is a built-in Python function or a Django utility that can do the validation.

    .. todo::

        add `import validators` and study this library to see what can be removed and/or refactored here
        see https://python-validators.github.io/validators/
    """

    LOCAL_HOSTS = ["localhost", "127.0.0.1"]
    LOCAL_HOSTS += [host + ":8000" for host in LOCAL_HOSTS]
    LOCAL_HOSTS.append("testserver")
    """List of local hosts used for validation purposes."""

    LOCAL_URLS = [f"http://{host}" for host in LOCAL_HOSTS] + [f"https://{host}" for host in LOCAL_HOSTS]
    """List of local URLs used for validation purposes."""

    VALID_ACCOUNT_NUMBER_PATTERN = r"^\d{4}-\d{4}-\d{4}$"
    """Pattern for validating Smarter account numbers."""

    VALID_PORT_PATTERN = r"^[0-9]{1,5}$"
    """Pattern for validating port numbers."""

    VALID_URL_PATTERN = r"^(http|https)://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(:[0-9]{1,5})?$"
    """Pattern for validating URLs."""

    VALID_HOSTNAME_PATTERN = r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$"
    """Pattern for validating hostnames."""

    VALID_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    """Pattern for validating UUIDs."""

    VALID_SESSION_KEY = r"^[a-fA-F0-9]{64}$"
    """Pattern for validating Smarter session keys."""

    VALID_SEMANTIC_VERSION = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(\+[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*)?$"
    """Pattern for validating semantic version strings."""

    VALID_URL_FRIENDLY_STRING = (
        r"^((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*$"
    )
    """Pattern for validating URL-friendly strings."""

    VALID_CLEAN_STRING = r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.[A-Za-z0-9_-]{1,63})*$"
    """Pattern for validating clean strings."""

    VALID_CLEAN_STRING_WITH_SPACES = r"^[\w\-\.~:\/\?#\[\]@!$&'()*+,;= %]+$"
    """Pattern for validating clean strings that may include spaces."""

    VALID_URL_ENDPOINT = r"^/[a-zA-Z0-9/_\-\{\}]+/$"  # NOTE: this allows placeholders like {id} in the url
    """Pattern for validating URL endpoints."""

    VALID_CAMEL_CASE = r"^[a-zA-Z0-9]+(?:[A-Z][a-z0-9]+)*$"
    """Pattern for validating camel case strings."""

    VALID_SNAKE_CASE = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
    """Pattern for validating snake case strings."""

    VALID_PASCAL_CASE = r"^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)*$"
    """Pattern for validating pascal case strings."""

    ACCOUNT_ACCOUNT_NUMBER_REGEX = r"\b\d{4}-\d{4}-\d{4}\b"
    """Regex for matching Smarter account numbers in text."""

    @staticmethod
    def validate_camel_case(value: str) -> str:
        """Validate camel case format

        Checks if the provided string is in camel case format.

        :param value: The string to validate.
        :type value: str
        :raises AMValueError: If the value is not in camel case format.
        :returns: The validated camel case string.
        :rtype: str

        Example::

            AMValidator.validate_camel_case("myCamelCase")  # returns "myCamelCase"
            AMValidator.validate_camel_case("NotCamelCase")  # raises AMValueError

        """
        if not re.match(AMValidator.VALID_CAMEL_CASE, value):
            raise AMValueError(f"Invalid camel case {value}")
        if not value:
            raise AMValueError("Value cannot be empty")
        if not value[0].islower():
            raise AMValueError(f"Value must start with a lowercase letter: {value}")
        if not value[0].isalpha():
            raise AMValueError(f"Value must start with a letter: {value}")
        if not value[1:].isalnum():
            raise AMValueError(f"Value must be in camel case format: {value}")
        if not value[1:].isalpha():
            raise AMValueError(f"Value must be in camel case format: {value}")
        return value

    @staticmethod
    def is_valid_camel_case(value: str) -> bool:
        """Check if the value is valid camel case

        Checks whether the provided string is in camel case format.

        :param value: The string to check.
        :type value: str
        :returns: True if the value is valid camel case, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_camel_case("myCamelCase")  # returns True
            AMValidator.is_valid_camel_case("NotCamelCase")  # returns False

        """
        try:
            AMValidator.validate_camel_case(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_snake_case(value: str) -> None:
        """Validate snake case format

        Checks if the provided string is in snake case format.

        :param value: The string to validate.
        :type value: str
        :raises AMValueError: If the value is not in snake case format.
        :returns: None if the value is valid.
        :rtype: None

        Example::

            AMValidator.validate_snake_case("my_snake_case")  # returns None
            AMValidator.validate_snake_case("NotSnakeCase")   # raises AMValueError

        """
        if not re.match(AMValidator.VALID_SNAKE_CASE, value):
            raise AMValueError(f"Invalid snake case {value}")
        if not value:
            raise AMValueError("Value cannot be empty")
        if not value[0].islower():
            raise AMValueError(f"Value must start with a lowercase letter: {value}")
        if not value[0].isalpha():
            raise AMValueError(f"Value must start with a letter: {value}")
        return

    @staticmethod
    def is_valid_snake_case(value: str) -> bool:
        """Check if the value is valid snake case

        Checks whether the provided string is in snake case format.

        :param value: The string to check.
        :type value: str
        :returns: True if the value is valid snake case, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_snake_case("my_snake_case")  # returns True
            AMValidator.is_valid_snake_case("NotSnakeCase")   # returns False

        """
        try:
            AMValidator.validate_snake_case(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_pascal_case(value: str) -> str:
        """Validate pascal case format

        Checks if the provided string is in pascal case format.

        :param value: The string to validate.
        :type value: str
        :raises AMValueError: If the value is not in pascal case format.
        :returns: The validated pascal case string.
        :rtype: str

        Example::

            AMValidator.validate_pascal_case("MyPascalCase")  # returns "MyPascalCase"
            AMValidator.validate_pascal_case("notPascalCase") # raises AMValueError

        """
        if not re.match(AMValidator.VALID_PASCAL_CASE, value):
            raise AMValueError(f"Invalid pascal case {value}")
        if not value:
            raise AMValueError("Value cannot be empty")
        if not value[0].isupper():
            raise AMValueError(f"Value must start with an uppercase letter: {value}")
        if not value[0].isalpha():
            raise AMValueError(f"Value must start with a letter: {value}")
        if not value[1:].islower():
            raise AMValueError(f"Value must be in pascal case format: {value}")
        if not value[1:].isalnum():
            raise AMValueError(f"Value must be in pascal case format: {value}")
        if not value[1:].isalpha():
            raise AMValueError(f"Value must be in pascal case format: {value}")
        return value

    @staticmethod
    def is_valid_pascal_case(value: str) -> bool:
        """Check if the value is valid pascal case

        Checks whether the provided string is in pascal case format.

        :param value: The string to check.
        :type value: str
        :returns: True if the value is valid pascal case, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_pascal_case("MyPascalCase")  # returns True
            AMValidator.is_valid_pascal_case("notPascalCase") # returns False

        """
        try:
            AMValidator.validate_pascal_case(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_json(value: str) -> Optional[str]:
        """Validate JSON format

        Checks if the provided string is valid JSON.

        :param value: The string to validate.
        :type value: str
        :raises AMValueError: If the value is not valid JSON.
        :returns: The validated JSON string.
        :rtype: str

        Example::

            AMValidator.validate_json('{"key": "value"}')  # returns '{"key": "value"}'
            AMValidator.validate_json('not json')          # raises AMValueError

        """
        try:
            if not isinstance(value, str):
                raise AMValueError("Value must be a string")
            if not value.strip():
                return
            json.loads(value)
        except (ValueError, TypeError) as e:
            raise AMValueError(f"Invalid JSON value {value}") from e
        return value

    @staticmethod
    def is_valid_json(value: str) -> bool:
        """Check if the value is valid JSON

        Checks whether the provided string is valid JSON.

        :param value: The string to check.
        :type value: str
        :returns: True if the value is valid JSON, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_json('{"key": "value"}')  # returns True
            AMValidator.is_valid_json('not json')          # returns False

        """
        try:
            AMValidator.validate_json(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_semantic_version(version: str) -> str:
        """Validate semantic version format (e.g., 1.12.1)

        Checks if the provided string is a valid semantic version.

        :param version: The version string to validate.
        :type version: str
        :raises AMValueError: If the version is not a valid semantic version.
        :returns: The validated semantic version string.
        :rtype: str

        Example::

            AMValidator.validate_semantic_version("1.2.3")    # returns "1.2.3"
            AMValidator.validate_semantic_version("1.2")      # raises AMValueError

        """
        if not re.match(AMValidator.VALID_SEMANTIC_VERSION, version):
            raise AMValueError(f"Invalid semantic version {version}")
        return version

    @staticmethod
    def is_valid_semantic_version(version: str) -> bool:
        """Check if the semantic version is valid

        Checks whether the provided string is a valid semantic version.

        :param version: The version string to check.
        :type version: str
        :returns: True if the version is valid semantic version, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_semantic_version("1.2.3")    # returns True
            AMValidator.is_valid_semantic_version("1.2")      # returns False

        """
        try:
            AMValidator.validate_semantic_version(version)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_is_not_none(value: str) -> str:
        """Validate that the value is not None

        Checks if the provided value is not None and not empty.

        :param value: The value to validate.
        :type value: str
        :raises AMValueError: If the value is None or empty.
        :returns: The validated value.
        :rtype: str

        Example::

            AMValidator.validate_is_not_none("something")  # returns "something"
            AMValidator.validate_is_not_none(None)         # raises AMValueError

        """
        if value is None:
            raise AMValueError("Value cannot be None")
        if not value:
            raise AMValueError("Value cannot be empty")
        return value

    @staticmethod
    def is_not_none(value: str) -> bool:
        """Check if the value is not None

        Checks whether the provided value is not None and not empty.

        :param value: The value to check.
        :type value: str
        :returns: True if the value is not None and not empty, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_not_none("something")  # returns True
            AMValidator.is_not_none(None)         # returns False

        """
        try:
            AMValidator.validate_is_not_none(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def validate_account_number(account_number: str) -> str:
        """Validate account number format

        Checks if the provided string is a valid account number in the format XXXX-XXXX-XXXX.

        :param account_number: The account number to validate.
        :type account_number: str
        :raises AMValueError: If the account number is not valid.
        :returns: The validated account number.
        :rtype: str

        Example::

            AMValidator.validate_account_number("1234-5678-9012")  # returns "1234-5678-9012"
            AMValidator.validate_account_number("invalid")         # raises AMValueError

        """
        if not re.match(AMValidator.VALID_ACCOUNT_NUMBER_PATTERN, account_number):
            raise AMValueError(f"Invalid account number {account_number}")
        return account_number

    @staticmethod
    def validate_domain(domain: Optional[str]) -> Optional[str]:
        """Validate domain format

        Checks if the provided string is a valid domain.

        :param domain: The domain to validate.
        :type domain: Optional[str]
        :raises AMValueError: If the domain is not valid.
        :returns: The validated domain or None.
        :rtype: Optional[str]

        Example::

            AMValidator.validate_domain("example.com")  # returns "example.com"
            AMValidator.validate_domain("invalid_domain")  # raises AMValueError

        """
        if isinstance(domain, str) and domain not in AMValidator.LOCAL_HOSTS + [None, ""]:
            AMValidator.validate_hostname(domain.split(":")[0])
            AMValidator.validate_url("http://" + domain)
        return domain

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format

        Checks if the provided string is a valid email address.

        :param email: The email address to validate.
        :type email: str
        :raises AMValueError: If the email address is not valid.
        :returns: The validated email address.
        :rtype: str

        Example::

            AMValidator.validate_email("user@example.com")  # returns "user@example.com"
            AMValidator.validate_email("invalid")           # raises AMValueError

        """
        try:
            validate_email(email)
        except ValidationError as e:
            raise AMValueError(f"Invalid email {email}") from e
        return email

    @staticmethod
    def validate_ip(ip: str) -> str:
        """Validate IP address format

        Checks if the provided string is a valid IP address.

        :param ip: The IP address to validate.
        :type ip: str
        :raises AMValueError: If the IP address is not valid.
        :returns: The validated IP address.
        :rtype: str

        Example::

            AMValidator.validate_ip("192.168.1.1")  # returns "192.168.1.1"
            AMValidator.validate_ip("invalid")      # raises AMValueError

        """
        try:
            validate_ipv4_address(ip)
        except ValidationError as e:
            raise AMValueError(f"Invalid IP address {ip}") from e
        return ip

    @staticmethod
    def validate_port(port: str) -> str:
        """Validate port format

        Checks if the provided string is a valid port number.

        :param port: The port to validate.
        :type port: str
        :raises AMValueError: If the port is not valid.
        :returns: The validated port.
        :rtype: str

        Example::

            AMValidator.validate_port("8080")  # returns "8080"
            AMValidator.validate_port("99999") # raises AMValueError

        """
        if not re.match(AMValidator.VALID_PORT_PATTERN, port):
            raise AMValueError(f"Invalid port {port}")
        if not port.isdigit():
            raise AMValueError(f"Port must be numeric: {port}")
        port_num = int(port)
        if not (0 <= port_num <= 65535):
            raise AMValueError(f"Port out of range (0-65535): {port}")
        return port

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format

        Checks if the provided string is a valid URL.

        :param url: The URL to validate.
        :type url: str
        :raises AMValueError: If the URL is not valid.
        :returns: The validated URL.
        :rtype: str

        Example::

            AMValidator.validate_url("https://example.com")  # returns "https://example.com"
            AMValidator.validate_url("invalid_url")          # raises AMValueError

        """
        valid_protocols = ["http", "https"]
        if not url:
            raise AMValueError(f"Invalid url {url}")
        if not isinstance(url, str):
            raise AMValueError(f"Invalid url {url}. Should be a string")
        try:
            if any(local_url in url for local_url in AMValidator.LOCAL_URLS):
                return url
        except TypeError:
            pass
        try:
            validator = URLValidator(schemes=valid_protocols)
            validator(url)
            parsed = urlparse(url)
            if parsed.hostname:
                AMValidator.validate_hostname(parsed.hostname)
        except ValidationError as e:
            parsed = urlparse(url)
            if parsed.scheme not in valid_protocols:
                raise AMValueError(f"Invalid url protocol {parsed.scheme}") from e
            if all([parsed.scheme, parsed.netloc]) or url.startswith("localhost"):
                return url
            if AMValidator.is_valid_ip(url):
                return url
            if validators.url(url):
                parsed = urlparse(url)
                if parsed.scheme in valid_protocols:
                    return url
            raise AMValueError(f"Invalid url {url}") from e
        return url

    @staticmethod
    def validate_hostname(hostname: str) -> str:
        """Validate hostname format

        Checks if the provided string is a valid hostname.

        :param hostname: The hostname to validate.
        :type hostname: str
        :raises AMValueError: If the hostname is not valid.
        :returns: The validated hostname.
        :rtype: str

        Example::

            AMValidator.validate_hostname("example.com")  # returns "example.com"
            AMValidator.validate_hostname("invalid_hostname!")  # raises AMValueError

        """
        if ":" in hostname:
            hostname, port = hostname.split(":")
            if not port.isdigit() or not 0 <= int(port) <= 65535:
                raise AMValueError(f"Invalid port {port}")
        if len(hostname) > 255:
            raise AMValueError(f"Invalid hostname {hostname}")
        if hostname[-1] == ".":
            hostname = hostname[:-1]  # strip exactly one dot from the right, if present
        allowed = re.compile(AMValidator.VALID_HOSTNAME_PATTERN, re.IGNORECASE)
        if all(allowed.match(x) for x in hostname.split(".")):
            return hostname
        raise AMValueError(f"Invalid hostname {hostname}")

    @staticmethod
    def validate_uuid(uuid: str) -> str:
        """Validate UUID format

        Checks if the provided string is a valid UUID.

        :param uuid: The UUID string to validate.
        :type uuid: str
        :raises AMValueError: If the UUID is not valid.
        :returns: The validated UUID.
        :rtype: str

        Example::

            AMValidator.validate_uuid("123e4567-e89b-12d3-a456-426614174000")  # returns the UUID
            AMValidator.validate_uuid("invalid")  # raises AMValueError

        """
        if not re.match(AMValidator.VALID_UUID_PATTERN, uuid):
            raise AMValueError(f"Invalid UUID {uuid}")
        return uuid

    @staticmethod
    def validate_clean_string(v: str) -> str:
        """Validate clean string format

        Checks if the provided string is a valid "clean" string (alphanumeric, underscores, or hyphens, and may include dots).

        :param v: The string to validate.
        :type v: str
        :raises AMValueError: If the string is not a valid clean string.
        :returns: The validated clean string.
        :rtype: str

        Example::

            AMValidator.validate_clean_string("valid_string-123")  # returns "valid_string-123"
            AMValidator.validate_clean_string("invalid string!")   # raises AMValueError

        """
        if not re.match(AMValidator.VALID_CLEAN_STRING, v):
            raise AMValueError(f"Invalid clean string {v}")
        return v

    @staticmethod
    def validate_http_request_header_key(key: str) -> str:
        """
        Validate HTTP request header key format

        HTTP header name must be ASCII and cannot contain special characters like ()<>@,;:\"/[]?={} \t

        :param key: The HTTP header key to validate.
        :type key: str
        :raises AMValueError: If the header key contains invalid characters or is not ASCII.
        :returns: The validated header key.
        :rtype: str

        Example::

            AMValidator.validate_http_request_header_key("X-Custom-Header")  # returns "X-Custom-Header"
            AMValidator.validate_http_request_header_key("Invalid Header!")  # raises AMValueError

        """
        if not key.isascii() or not re.match(r"^[!#$%&'*+\-.^_`|~0-9a-zA-Z]+$", key):
            raise AMValueError("Header name contains invalid characters or is not ASCII.")
        return key

    @staticmethod
    def validate_http_request_header_value(value: str) -> str:
        """
        Validate HTTP request header value format
        HTTP header value must not contain control characters like escaped nor special characters.

        :param value: The HTTP header value to validate.
        :type value: str
        :raises AMValueError: If the header value contains invalid characters.
        :returns: The validated header value.
        :rtype: str

        """
        if not re.match(r"^[\t\x20-\x7E\x80-\xFF]*$", value):
            raise AMValueError("Header value contains invalid characters (e.g., control characters).")
        return value

    # --------------------------------------------------------------------------
    # boolean helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def is_valid_http_request_header_key(key: str) -> bool:
        """Check if HTTP request header key is valid

        Checks whether the provided HTTP request header key is valid.

        :param key: The HTTP header key to check.
        :type key: str
        :returns: True if the header key is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_http_request_header_key("X-Custom-Header")  # returns True
            AMValidator.is_valid_http_request_header_key("Invalid Header!")  # returns False

        """
        try:
            AMValidator.validate_http_request_header_key(key)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_http_request_header_value(value: str) -> bool:
        """Check if HTTP request header value is valid

        Checks whether the provided HTTP request header value is valid.

        :param value: The HTTP header value to check.
        :type value: str
        :returns: True if the header value is valid, otherwise False.
        :rtype: bool
        """
        try:
            AMValidator.validate_http_request_header_value(value)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_account_number(account_number: str) -> bool:
        """Check if account number is valid

        Checks whether the provided account number is valid.

        :param account_number: The account number to check.
        :type account_number: str
        :returns: True if the account number is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_account_number("1234-5678-9012")  # returns True
            AMValidator.is_valid_account_number("invalid")         # returns False

        """
        try:
            AMValidator.validate_account_number(account_number)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        """Check if domain is valid

        Checks whether the provided domain is valid.

        :param domain: The domain to check.
        :type domain: str
        :returns: True if the domain is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_domain("example.com")      # returns True
            AMValidator.is_valid_domain("invalid_domain")   # returns False

        """
        try:
            AMValidator.validate_domain(domain)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Check if email is valid

        Checks whether the provided email address is valid.

        :param email: The email address to check.
        :type email: str
        :returns: True if the email address is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_email("user@example.com")  # returns True
            AMValidator.is_valid_email("invalid")           # returns False

        """
        try:
            AMValidator.validate_email(email)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Check if IP address is valid

        Checks whether the provided IP address is valid.

        :param ip: The IP address to check.
        :type ip: str
        :returns: True if the IP address is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_ip("192.168.1.1")  # returns True
            AMValidator.is_valid_ip("invalid")      # returns False

        """
        try:
            AMValidator.validate_ip(ip)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_port(port: str) -> bool:
        """Check if port is valid

        Checks whether the provided port is valid.

        :param port: The port to check.
        :type port: str
        :returns: True if the port is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_port("8080")  # returns True
            AMValidator.is_valid_port("invalid")  # returns False

        """
        try:
            AMValidator.validate_port(port)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid

        Checks whether the provided URL is valid.

        :param url: The URL to check.
        :type url: str
        :returns: True if the URL is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_url("https://example.com")  # returns True
            AMValidator.is_valid_url("invalid_url")          # returns False

        """
        try:
            AMValidator.validate_url(url)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_hostname(hostname: str) -> bool:
        """Check if URL is valid

        Checks whether the provided URL is valid.

        :param url: The URL to check.
        :type url: str
        :returns: True if the URL is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_url("https://example.com")  # returns True
            AMValidator.is_valid_url("invalid_url")          # returns False

        """
        try:
            AMValidator.validate_hostname(hostname)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_uuid(uuid: str) -> bool:
        """Check if UUID is valid

        Checks whether the provided UUID is valid.

        :param uuid: The UUID string to check.
        :type uuid: str
        :returns: True if the UUID is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_uuid("123e4567-e89b-12d3-a456-426614174000")  # returns True
            AMValidator.is_valid_uuid("invalid")                                # returns False

        """
        try:
            AMValidator.validate_uuid(uuid)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_cleanstring(v: str) -> bool:
        """Check if hostname is valid

        Checks whether the provided hostname is valid.

        :param hostname: The hostname to check.
        :type hostname: str
        :returns: True if the hostname is valid, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_hostname("example.com")         # returns True
            AMValidator.is_valid_hostname("invalid_hostname!")   # returns False

        """
        try:
            AMValidator.validate_clean_string(v)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_valid_url_endpoint(url: str) -> bool:
        """
        Check if the URL is valid and ends with a trailing slash.

        Checks whether the provided URL is valid and ends with a trailing slash.

        :param url: The URL to check.
        :type url: str
        :returns: True if the URL is valid and ends with a trailing slash, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_valid_url_endpoint("/api/v1/tests/unauthenticated/list/")  # returns True
            AMValidator.is_valid_url_endpoint("/api/v1/tests/unauthenticated/list")   # returns False

        """
        try:
            AMValidator.validate_url_endpoint(url)
            return True
        except AMValueError:
            return False

    @staticmethod
    def is_api_endpoint(url: str) -> bool:
        """
        Check if the URL is an API endpoint.

        Checks whether the provided URL contains '/api/'.

        :param url: The URL to check.
        :type url: str
        :returns: True if the URL is an API endpoint, otherwise False.
        :rtype: bool

        Example::

            AMValidator.is_api_endpoint("/api/v1/tests/unauthenticated/list/")  # returns True
            AMValidator.is_api_endpoint("/v1/tests/unauthenticated/list/")      # returns False

        """
        if not isinstance(url, str):
            return False

        if "/api/" in url:
            # checks for /api/ in the full url: example.com/api/v1/
            return True

        try:
            if ACCOUNT_API_SUBDOMAIN in str(AMValidator.base_url(url)):
                # checks for api subdomain in base url: api.example.com
                return True
        except AMValueError:
            return False

        return False

    # --------------------------------------------------------------------------
    # list helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def validate_url_endpoint(url: str) -> None:
        """
        Validate URL endpoint format

        Checks if the provided string is a valid URL endpoint (must start and end with a slash).

        :param url: The URL endpoint to validate.
        :type url: str
        :raises AMValueError: If the URL endpoint is not valid.
        :returns: None if the URL endpoint is valid.
        :rtype: None

        Example::

            AMValidator.validate_url_endpoint("/api/v1/tests/unauthenticated/list/")  # returns None
            AMValidator.validate_url_endpoint("/api/v1/tests/unauthenticated/list")   # raises AMValueError

        """
        if not re.match(AMValidator.VALID_URL_ENDPOINT, url):
            raise AMValueError(f"URL endpoint '{url}' contains invalid characters.")
        if not url.startswith("/"):
            raise AMValueError(f"Invalid URL endpoint '{url}'. Should start with a leading slash")
        if not url.endswith("/"):
            raise AMValueError(f"Invalid URL endpoint '{url}'. Should end with a trailing slash")

    @staticmethod
    def validate_list_of_account_numbers(account_numbers: list) -> None:
        """Validate list of account numbers

        Checks if each item in the provided list is a valid account number.

        :param account_numbers: The list of account numbers to validate.
        :type account_numbers: list
        :raises AMValueError: If any account number in the list is not valid.
        :returns: None if all account numbers are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_account_numbers(["1234-5678-9012", "2345-6789-0123"])  # returns None
            AMValidator.validate_list_of_account_numbers(["invalid", "2345-6789-0123"])         # raises AMValueError

        """
        for account_number in account_numbers:
            AMValidator.validate_account_number(account_number)

    @staticmethod
    def validate_list_of_domains(domains: list) -> None:
        """Validate list of domains

        Checks if each item in the provided list is a valid domain.

        :param domains: The list of domains to validate.
        :type domains: list
        :raises AMValueError: If any domain in the list is not valid.
        :returns: None if all domains are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_domains(["example.com", "test.com"])  # returns None
            AMValidator.validate_list_of_domains(["invalid_domain", "test.com"])  # raises AMValueError

        """
        for domain in domains:
            AMValidator.validate_domain(domain)

    @staticmethod
    def validate_list_of_emails(emails: list) -> None:
        """Validate list of emails

        Checks if each item in the provided list is a valid email address.

        :param emails: The list of email addresses to validate.
        :type emails: list
        :raises AMValueError: If any email address in the list is not valid.
        :returns: None if all email addresses are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_emails(["user@example.com", "admin@test.com"])  # returns None
            AMValidator.validate_list_of_emails(["invalid", "admin@test.com"])           # raises AMValueError

        """
        for email in emails:
            AMValidator.validate_email(email)

    @staticmethod
    def validate_list_of_ips(ips: list) -> None:
        """Validate list of IP addresses

        Checks if each item in the provided list is a valid IP address.

        :param ips: The list of IP addresses to validate.
        :type ips: list
        :raises AMValueError: If any IP address in the list is not valid.
        :returns: None if all IP addresses are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_ips(["192.168.1.1", "10.0.0.1"])  # returns None
            AMValidator.validate_list_of_ips(["invalid", "10.0.0.1"])      # raises AMValueError

        """
        for ip in ips:
            AMValidator.validate_ip(ip)

    @staticmethod
    def validate_list_of_ports(ports: list) -> None:
        """
        Validate list of ports

        Checks if each item in the provided list is a valid port.

        :param ports: The list of ports to validate.
        :type ports: list
        :raises AMValueError: If any port in the list is not valid.
        :returns: None if all ports are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_ports(["8080", "443"])    # returns None
            AMValidator.validate_list_of_ports(["invalid", "443"]) # raises AMValueError

        """
        for port in ports:
            AMValidator.validate_port(port)

    @staticmethod
    def validate_list_of_urls(urls: list) -> None:
        """Validate list of URLs

        Checks if each item in the provided list is a valid URL.

        :param urls: The list of URLs to validate.
        :type urls: list
        :raises AMValueError: If any URL in the list is not valid.
        :returns: None if all URLs are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_urls(["https://example.com", "https://test.com"])  # returns None
            AMValidator.validate_list_of_urls(["invalid_url", "https://test.com"])          # raises AMValueError

        """
        for url in urls:
            AMValidator.validate_url(url)

    @staticmethod
    def validate_list_of_uuids(uuids: list) -> None:
        """Validate list of UUIDs

        Checks if each item in the provided list is a valid UUID.

        :param uuids: The list of UUIDs to validate.
        :type uuids: list
        :raises AMValueError: If any UUID in the list is not valid.
        :returns: None if all UUIDs are valid.
        :rtype: None

        Example::

            AMValidator.validate_list_of_uuids([
                "123e4567-e89b-12d3-a456-426614174000",
                "987e6543-e21b-12d3-a456-426614174111"
            ])  # returns None

            AMValidator.validate_list_of_uuids([
                "invalid",
                "987e6543-e21b-12d3-a456-426614174111"
            ])  # raises AMValueError

        """
        for uuid in uuids:
            AMValidator.validate_uuid(uuid)

    # --------------------------------------------------------------------------
    # utility helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def base_domain(url: str) -> Optional[str]:
        """
        Get the base domain from a URL.

        Extracts the base domain from the provided URL string.

        :param url: The URL string to extract the base domain from.
        :type url: str
        :returns: The base domain as a string, or None if not found.
        :rtype: Optional[str]

        Example::

            AMValidator.base_domain("https://example.com/path/")  # returns "example.com"
            AMValidator.base_domain("")                           # returns None

        """
        if not url:
            return None
        base_url = AMValidator.base_url(url)
        if not base_url:
            return None
        base_url = base_url.replace("http://", "").replace("https://", "")
        return base_url.rstrip("/")

    @staticmethod
    def base_url(url: str) -> Optional[str]:
        """
        Get the base URL from a URL.

        Extracts the base URL from the provided URL string.

        :param url: The URL string to extract the base URL from.
        :type url: str
        :returns: The base URL as a string, or None if not found.
        :rtype: Optional[str]

        Example::

            AMValidator.base_url("https://example.com/path/")  # returns "https://example.com"
            AMValidator.base_url("")                           # returns None

        """
        if not url:
            return None
        AMValidator.validate_url(url)
        parsed_url = urlparse(url)
        unparsed_url = urlunparse((parsed_url.scheme, parsed_url.netloc, "", "", "", ""))
        return AMValidator.trailing_slash(unparsed_url)

    @staticmethod
    def trailing_slash(url: str) -> Optional[str]:
        """
        ensure that URL ends with a trailing slash

        Appends a trailing slash to the URL if it does not already have one.

        :param url: The URL to process.
        :type url: str
        :returns: The URL with a trailing slash, or None if the input is empty.
        :rtype: Optional[str]

        Example::

            AMValidator.trailing_slash("https://example.com")   # returns "https://example.com/"
            AMValidator.trailing_slash("https://example.com/")  # returns "https://example.com/"
            AMValidator.trailing_slash("")                      # returns None

        """
        if not url:
            return None
        return url if url.endswith("/") else url + "/"

    @staticmethod
    def urlify(url: str, scheme: Optional[str] = None, environment: str = AMEnvironments.LOCAL) -> str:
        """
        ensure that URL starts with http:// or https://
        and ends with a trailing slash

        Ensures the provided URL starts with a valid scheme (http or https) and ends with a trailing slash.

        :param url: The URL to process.
        :type url: str
        :param scheme: (Optional) The scheme to use ("http" or "https"). Deprecated.
        :type scheme: Optional[str]
        :param environment: The environment to determine the default scheme.
        :type environment: str
        :returns: The normalized URL with scheme and trailing slash.
        :rtype: str

        Example::

            AMValidator.urlify("example.com")                # returns "https://example.com/"
            AMValidator.urlify("example.com", scheme="http") # returns "http://example.com/"
            AMValidator.urlify("https://example.com")        # returns "https://example.com/"

        """
        logger.debug("urlify %s, %s", url, scheme)
        if not url:
            raise AMValueError("URL cannot be empty")
        if scheme:
            warnings.warn("scheme is deprecated and will be removed in a future release.", DeprecationWarning)
        if scheme and scheme not in ["http", "https"]:
            AMValidator.raise_error(f"Invalid scheme {scheme}. Should be one of ['http', 'https']")
        scheme = "http" if environment == AMEnvironments.LOCAL else "https"
        if not "://" in url:
            url = f"{scheme}://{url}"
        parsed_url = urlparse(url)
        retval = urlunparse((scheme, parsed_url.netloc, parsed_url.path, "", "", ""))
        retval = AMValidator.trailing_slash(url)
        if not retval:
            raise AMValueError(f"Invalid URL {url}")
        AMValidator.validate_url(retval)
        if not retval.endswith("/"):
            retval += "/"
        return retval

    @staticmethod
    def raise_error(msg: str) -> None:
        """Raise a AMValueError with the given message"""
        raise AMValueError(msg)
