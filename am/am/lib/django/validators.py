"""
Internal validation features.

This module contains functions for validating various data types.
Before adding anything to this module, please first check if there is a built-in Python function
or a Django utility that can do the validation.
"""

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email, validate_ipv4_address

from am.common.const import ACCOUNT_API_SUBDOMAIN, AMEnvironments
from am.common.exceptions import AMValueError


class AMValidator:
    """
    Class for validating various data types.

    Before adding anything to this class, please
    first check if there is a built-in Python function or a Django utility that can do the validation.
    """

    LOCAL_HOSTS = ["localhost", "127.0.0.1"]
    LOCAL_HOSTS += [host + ":8000" for host in LOCAL_HOSTS]
    LOCAL_HOSTS.append("testserver")
    """List of local hosts used for validation purposes."""

    LOCAL_URLS = [f"http://{host}" for host in LOCAL_HOSTS] + [f"https://{host}" for host in LOCAL_HOSTS]
    """List of local URLs used for validation purposes."""

    VALID_ACCOUNT_NUMBER_PATTERN = r"^\d{4}-\d{4}-\d{4}$"
    """Pattern for validating Smarter account numbers."""

    VALID_HOSTNAME_PATTERN = r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$"
    """Pattern for validating hostnames."""

    ACCOUNT_ACCOUNT_NUMBER_REGEX = r"\b\d{4}-\d{4}-\d{4}\b"
    """Regex for matching Smarter account numbers in text."""

    @staticmethod
    def validate_account_number(account_number: str) -> str:
        """Validate account number format.

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
        """Validate domain format.

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
        """Validate email format.

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
        """Validate IP address format.

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
    def validate_url(url: str) -> str:
        """Validate URL format.

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
        if any(local_url in url for local_url in AMValidator.LOCAL_URLS):
            return url
        try:
            URLValidator(schemes=valid_protocols)(url)
            parsed = urlparse(url)
            if parsed.hostname:
                AMValidator.validate_hostname(parsed.hostname)
        except ValidationError as e:
            # Django's URLValidator wants a top-level domain. Accept any http(s) url with a host.
            parsed = urlparse(url)
            if parsed.scheme not in valid_protocols:
                raise AMValueError(f"Invalid url protocol {parsed.scheme}") from e
            if parsed.netloc:
                return url
            raise AMValueError(f"Invalid url {url}") from e
        return url

    @staticmethod
    def validate_hostname(hostname: str) -> str:
        """Validate hostname format.

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

    # --------------------------------------------------------------------------
    # boolean helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Check if email is valid.

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
        """Check if IP address is valid.

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
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid.

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
        """Check if URL is valid.

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
    # utility helpers
    # --------------------------------------------------------------------------
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
        Ensure that URL ends with a trailing slash.

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
    def urlify(url: str, environment: str = AMEnvironments.LOCAL) -> str:
        """
        Ensure that a URL starts with http:// or https:// and ends with a trailing slash.

        A URL without a scheme gets ``http`` in the local environment and ``https`` in any other.

        :param url: The URL to process.
        :type url: str
        :param environment: The environment that determines the default scheme.
        :type environment: str
        :returns: The normalized URL with scheme and trailing slash.
        :rtype: str
        :raises AMValueError: If the URL is empty or invalid.

        Example::

            AMValidator.urlify("example.com")                       # returns "http://example.com/"
            AMValidator.urlify("example.com", environment="prod")   # returns "https://example.com/"
            AMValidator.urlify("https://example.com")               # returns "https://example.com/"
        """
        if not url:
            raise AMValueError("URL cannot be empty")
        if "://" not in url:
            scheme = "http" if environment == AMEnvironments.LOCAL else "https"
            url = f"{scheme}://{url}"
        retval = AMValidator.trailing_slash(url)
        AMValidator.validate_url(retval)  # type: ignore[arg-type]
        return retval  # type: ignore[return-value]
