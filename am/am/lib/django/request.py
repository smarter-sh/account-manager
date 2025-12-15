# pylint: disable=C0302
"""
Smarter request mixin.

This is a helper class for the Django request object that resolves
known url patterns. key features include:
- lazy loading of the user, account, user profile.
- meta data for describing chatbot characteristics.
- url parsing and validation.
- url pattern recognition.
- logging.
"""

import hashlib
import inspect
import logging
import re
from datetime import datetime
from functools import cached_property
from typing import Any, Optional, Union
from unittest.mock import MagicMock
from urllib.parse import ParseResult, urlparse, urlunsplit

import tldextract
import yaml
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpRequest, QueryDict
from rest_framework.request import Request as RestFrameworkRequest

from am.apps.account.mixins import AccountMixin
from am.apps.account.utils import (
    account_number_from_url,
    get_cached_account,
    get_cached_admin_user_for_account,
)
from am.common.conf import account_settings
from am.common.exceptions import AMValueError
from am.common.utils import (
    mask_string,
    rfc1034_compliant_to_snake,
    smarter_build_absolute_uri,
)
from am.lib import json
from am.lib.django import waffle
from am.lib.django.validators import AMValidator
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper


# Match netloc: chatbot_name.account_number.api.environment_api_domain
netloc_pattern_named_url = re.compile(
    rf"^(?P<chatbot_name>[a-zA-Z0-9\-]+)\.(?P<account_number>\d{{4}}-\d{{4}}-\d{{4}})\.api\.{re.escape(account_settings.environment_account_manager_domain)}(:\d+)?$"
)


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.REQUEST_MIXIN_LOGGING) and level >= account_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)

AMRequestType = Optional[Union[RestFrameworkRequest, HttpRequest, WSGIRequest, MagicMock]]
"""Type alias for all Account Manager request types."""


class AMRequestMixin(AccountMixin):
    """
    Helper class for the Django request object that enforces authentication and
    provides lazy loading of the user, account, user profile.

    This mixin works with any Django request object and any valid URL, but is designed
    as a helper class for Smarter ChatBot URLs.

    .. note::
        The request object is an optional positional argument due to Django view lifecycles,
        which do not recognize the request object until after class ``__init__()``.
        ``AMRequestMixin`` is included as a mixin in the Account Manager base view classes.

    **Valid endpoints:**

    2. Authenticated sandbox endpoints (authenticated chats)
       (``self.is_chatbot_sandbox_url == True``)

       - ``http://localhost:8000/workbench/<str:name>/`` → ``am.apps.prompt.views.ChatAppWorkbenchView``
       - ``http://localhost:8000/workbench/<str:name>/config/`` → ``am.apps.prompt.views.ChatConfigView``


    """

    __slots__ = (
        "_instance_id",
        "_am_request",
        "_timestamp",
        "_url",
        "_url_account_number",
        "_parse_result",
        "_params",
        "_session_key",
        "_data",
        "_cache_key",
    )

    # pylint: disable=W0613
    def __init__(self, request: Optional[HttpRequest], *args, **kwargs):
        self._instance_id = id(self)
        self._am_request: Optional[HttpRequest] = request
        self._timestamp = datetime.now()
        self._url: Optional[str] = None
        self._url_account_number: Optional[str] = None
        self._parse_result: ParseResult
        self._params: Optional[QueryDict] = None
        self._data: Optional[dict] = None
        self._cache_key: Optional[str] = None

        if request:
            self.am_request = request
        else:
            logger.debug(
                "%s.__init__() - request is None. AMRequestMixin will be partially initialized. This might affect request processing.",
                self.formatted_class_name,
            )
            super().__init__(request, *args, api_token=self.api_token, **kwargs)
        if self.am_request:
            self.am_request.user = self.user  # type: ignore

    def init(self, request: HttpRequest, *args, **kwargs):
        """
        Handles initializations that require a valid request.

        This method is called from ``__init__()`` if the request object is passed.
        It is also called from the ``am_request`` setter.

        Args:
            request (HttpRequest): Django HttpRequest object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Raises:
            AMValueError: If the request URL is missing or invalid.

        Example::

            from am.lib.django.request import AMRequestMixin

            class Foo(AMRequestMixin):
                pass

            foo = Foo(request)
            foo.init(request)
        """
        url = smarter_build_absolute_uri(self.am_request) if self.am_request else None

        logger.info(
            "%s.init() - initializing with request=%s, args=%s, kwargs=%s", self.formatted_class_name, url, args, kwargs
        )

        if url is None:
            raise AMValueError(
                f"{self.formatted_class_name}.__init__() - request url is None or empty. request={request}"
            )

        self._parse_result = urlparse(url)
        if not self._parse_result.scheme or not self._parse_result.netloc:
            raise AMValueError(f"{self.formatted_class_name} - request url is not a valid URL. url={url}")

        # rebuild the url minus any query parameters
        # example:
        # will return https://hr.3141-5926-5359.alpha.api.example.com/config/
        self._url = urlunsplit((self._parse_result.scheme, self._parse_result.netloc, self._parse_result.path, "", ""))
        self._url = AMValidator.urlify(self._url)

        super().__init__(request, *args, api_token=self.api_token, **kwargs)

        logger.info(
            "%s.init() - initializing with instance_id=%s, request=%s, args=%s, kwargs=%s auth_header=%s user_profile=%s, account=%s",
            self.formatted_class_name,
            self._instance_id,
            request,
            args,
            kwargs,
            request.META.get("HTTP_AUTHORIZATION") if request and hasattr(request, "META") else None,
            self.user_profile if self.user_profile else None,
            self.account if self.account else None,
        )

        if self.is_requestmixin_ready:
            self.helper_logger(
                f"init() {self._instance_id} initialized successfully url={self.url}, user={self.user_profile}"
            )
        else:
            msg = f"{self.formatted_class_name}.init() - request {self._instance_id} is not ready. request={self.am_request}"
            logger.warning(msg)

        logger.info("AMRequestMixin().init() - finished %s", self.dump())

    def invalidate_cached_properties(self):
        """
        Invalidates all cached properties on the instance to force re-evaluation.

        This method removes all attributes cached by `@cached_property` decorators
        from the instance's `__dict__`. It is useful for testing or when the request
        object changes and you need to ensure that all dependent properties are recalculated.

        Example::

            from am.lib.django.request import AMRequestMixin

            class Foo(AMRequestMixin):
                pass

            foo = Foo(request)
            foo.invalidate_cached_properties(request)

        Raises:
            None
        """
        for cls in self.__class__.__mro__:
            for name, value in inspect.getmembers(cls):
                if isinstance(value, cached_property):
                    self.__dict__.pop(name, None)

    @property
    def am_request(self) -> AMRequestType:
        """
        Returns the current request object.

        This property is named to avoid potential name collisions in child classes.
        This property is preferred over standard Django request types in that
        it more elegantly resolves idiosyncratic usage like Unit tests, Sphinx docs,
        and other non-standard request objects.

        Example::

            request_mixin = AMRequestMixin(request)
            req = request_mixin.am_request

        :return: The current request object.
        """
        return self._am_request

    @am_request.setter
    def am_request(self, request: AMRequestType):
        self._am_request = request
        if request is not None:
            logger.info(
                "%s.am_request setter called with request: %s",
                self.formatted_class_name,
                smarter_build_absolute_uri(request),
            )
            self.init(request)

    @cached_property
    def auth_header(self) -> Optional[str]:
        """Get the Authorization header from the request.

        :return: The value of the "Authorization" header if present, otherwise None.

        Example::

            request_mixin = AMRequestMixin(request)
            print(request_mixin.auth_header)

        :return: The Authorization header as a string, or None if not present.
        """
        return (
            self._am_request.META.get("HTTP_AUTHORIZATION")
            if self._am_request and hasattr(self._am_request, "META")
            else None
        )

    @cached_property
    def api_token(self) -> Optional[bytes]:
        """
        Get the API token from the request.

        :return: The API token as bytes if present in the Authorization header, otherwise None.

        Example::

            request_mixin = AMRequestMixin(request)
            token = request_mixin.api_token

        :return: The API token as bytes, or None if not present.
        """
        if isinstance(self.auth_header, str) and self.auth_header.startswith("Token "):
            return self.auth_header.split("Token ")[1].encode()
        return None

    @cached_property
    def qualified_request(self) -> bool:
        """
        A cursory screening of the WSGI request object to look for
        any disqualifying conditions that confirm this is not a
        request that we are interested in.

        The request is considered "qualified" if **all** of the following are true:

        - The request object (`self._am_request`) is present.
        - The URL path is present and non-empty.
        - The request does **not** originate from an internal AWS Kubernetes subnet (netloc starts with `192.168`).
        - The path is **not** in the list of `amnesty_urls`.
        - The path does **not** start with `/admin/`.
        - The path does **not** start with `/docs/`.
        - The path does **not** end with a static file extension (e.g., `.css`, `.js`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.woff`, `.woff2`, `.ttf`, `.eot`, `.ico`).

        :return: True if the request passes all checks and is of interest, otherwise False.

        Example::

            # True case: a valid chatbot request
            request_mixin = AMRequestMixin(request)
            if request_mixin.qualified_request:
                print("This is a qualified chatbot request.")

            # False case: a static asset or admin/docs request
            static_request = AMRequestMixin(static_asset_request)
            if not static_request.qualified_request:
                print("This request is not of interest.")

        """
        if not self._am_request:
            return False
        path = self._parse_result.path if self._parse_result else None
        if not path:
            return False

        if self.parsed_url and self.parsed_url.netloc and self.parsed_url.netloc[:7] == "192.168":
            # internal processes running in a AWS kubernetes internal subnet.
            # definitely not a chatbot request.
            return False

        if path in self.amnesty_urls:
            return False
        if path.startswith("/admin/"):
            return False
        if path.startswith("/docs/"):
            return False

        static_extensions = [
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".ico",
        ]
        if any(path.endswith(ext) for ext in static_extensions):
            return False

        return True

    @property
    def url(self) -> str:
        """
        The string representation of the ParseResult object stored in _parse_result.

        :return: The URL as a string.

        Example::

            request_mixin = AMRequestMixin(request)
            url_str = request_mixin.url
            print(url_str)  # e.g., 'https://example.com/path/'

        """
        if not isinstance(self._parse_result, ParseResult):
            raise AMValueError(
                f"The URL has not been initialized as a ParseResult. Received type: {type(self._parse_result)}"
            )
        if self._url:
            return self._url

        logger.error(
            "%s.url() property was accessed before it was initialized. request: %s",
            self.formatted_class_name,
            self.am_request,
        )
        raise AMValueError("The URL has not been initialized. Please check the request object.")

    @property
    def parsed_url(self) -> ParseResult:
        """
        Expose the private ParseResult URL object as a public property.

        :return: The parsed URL as a `ParseResult` object.

        Example::

            request_mixin = AMRequestMixin(request)
            parsed = request_mixin.parsed_url
            print(parsed.netloc)  # e.g., 'example.com'

        """
        if not isinstance(self._parse_result, ParseResult):
            raise AMValueError("The URL has not been initialized as a ParseResult.")
        return self._parse_result

    @property
    def url_path_parts(self) -> list:
        """
        Extract the path parts from the URL.

        :return: A list of strings representing each part of the URL path.

        Example::

            request_mixin = AMRequestMixin(request)
            parts = request_mixin.url_path_parts
            print(parts)  # e.g., ['api', 'v1', 'workbench', '1', 'chat']

        """
        return self.parsed_url.path.strip("/").split("/")

    @property
    def params(self) -> Optional[QueryDict]:
        """
        The query string parameters from the Django request object.

        This extracts the query string parameters from the request object and converts them to a dictionary.
        Used in child views to pass optional command-line parameters to the broker.

        :return: QueryDict containing the query string parameters.

        Example::

            request_mixin = AMRequestMixin(request)
            params = request_mixin.params
            print(params)  # e.g., {'uid': 'xyz'}

        """
        if not self._params:
            try:
                self._params = QueryDict(self.am_request.META.get("QUERY_STRING", ""))  # type: ignore
            except AttributeError as e:
                logger.error(
                    "%s.params() internal error. Could not parse query string parameters: %s",
                    self.formatted_class_name,
                    e,
                )
                return None
        return self._params

    @property
    def timestamp(self):
        """
        Create a consistent timestamp based on the time that this object was instantiated.

        :return: The timestamp as a `datetime` object.

        Example::

            request_mixin = AMRequestMixin(request)
            ts = request_mixin.timestamp
            print(ts)  # e.g., 2025-12-01 12:34:56.789012

        """
        return self._timestamp

    @property
    def data(self) -> Optional[Union[dict, list, str]]:
        """
        Get the request body data as a dictionary, list or str.

        :return: The request body data as a dict, list, or str, or None if not available.

        Example::

            request_mixin = AMRequestMixin(request)
            data = request_mixin.data
            print(data)  # e.g., {'key': 'abc123', ...}

        """
        if self._data:
            return self._data

        if not self.am_request:
            return None
        if not self.qualified_request:
            return None

        if not self.am_request:
            logger.warning("%s.data() - request is None or not set.", self.formatted_class_name)
            return {}
        try:
            body = self.am_request.body if hasattr(self.am_request, "body") else None
            if body is not None:
                body_str = body.decode("utf-8").strip()

                try:
                    self._data = json.loads(body_str) if isinstance(body_str, (str, bytearray, bytes)) else None
                    logger.info(
                        "%s.data() - initialized json from request body: %s",
                        self.formatted_class_name,
                        body_str,
                    )
                except json.JSONDecodeError:
                    try:
                        self._data = yaml.safe_load(body_str) if body_str else {}
                        logger.info(
                            "%s.data() - initialized json from parsed yaml request body: %s",
                            self.formatted_class_name,
                            body_str,
                        )
                    except yaml.YAMLError:
                        logger.error(
                            "%s.data() - failed to parse request body: %s",
                            self.formatted_class_name,
                            body_str,
                        )
                self._data = self._data or {}
        except json.JSONDecodeError:
            try:
                body = self.am_request.body if hasattr(self.am_request, "body") else None
                if body is not None:
                    body_str = body.decode("utf-8").strip()
                    self._data = yaml.safe_load(body_str) if body_str else {}
                    logger.info(
                        "%s.data() - initialized from parsed request body as yaml: %s",
                        self.formatted_class_name,
                        body_str,
                    )
            except yaml.YAMLError:
                logger.error(
                    "%s - failed to parse request body as JSON or YAML. request.body=%s",
                    self.formatted_class_name,
                    body_str,
                )

        self._data = self._data or {}
        self.helper_logger(f"request body json={self._data}")

        return self._data

    @cached_property
    def unique_client_string(self) -> str:
        """
        Generate a unique string based on several request attributes.

        This string is used for generating `client_key`.

        The unique string is composed of:
            - Account number
            - URL
            - User agent
            - IP address
            - Timestamp

        Returns:
            str: A unique string representing the client and request context.

        Example::

            request_mixin = AMRequestMixin(request)
            unique_str = request_mixin.unique_client_string
            print(unique_str)

        """
        if not self.am_request:
            return "unique_client_string"
        account_number = self.account.account_number if self.account else "####-####-####"
        url = self.url if self.url else "http://localhost:8000/"
        timestamp = self.timestamp.isoformat()
        return f"{account_number}.{url}.{self.user_agent}.{self.ip_address}.{timestamp}"

    @cached_property
    def ip_address(self) -> Optional[str]:
        """
        Get the client's IP address from the request object.

        This property attempts to extract the IP address from the request's META dictionary,
        using the "REMOTE_ADDR" key. If the IP address is not available, it returns None.

        Returns:
            Optional[str]: The client's IP address as a string, or None if not found.

        Example::

            request_mixin = AMRequestMixin(request)
            ip = request_mixin.ip_address
            print(ip)  # e.g., '192.168.1.100'

        """
        if self.am_request is not None and hasattr(self.am_request, "META") and isinstance(self.am_request.META, dict):
            return self.am_request.META.get("REMOTE_ADDR", "") or "ip_address"
        return None

    @cached_property
    def user_agent(self) -> Optional[str]:
        """
        Get the client's user agent string from the request object.

        This property attempts to extract the user agent from the request's META dictionary,
        using the "HTTP_USER_AGENT" key. If the user agent is not available, it returns a default value.

        Returns:
            Optional[str]: The client's user agent string, or None if not found.

        Example::

            request_mixin = AMRequestMixin(request)
            ua = request_mixin.user_agent
            print(ua)  # e.g., 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'

        """
        if self.am_request is not None and hasattr(self.am_request, "META") and isinstance(self.am_request.META, dict):
            # META is a dictionary-like object containing all HTTP headers
            # and other request metadata.
            # HTTP_USER_AGENT is the standard header for user agent information.
            # If it doesn't exist, we return a default value.
            # This is useful for debugging and logging purposes.
            return self.am_request.META.get("HTTP_USER_AGENT", "user_agent")
        return None

    @cached_property
    def is_environment_root_domain(self) -> bool:
        """
        Returns True if the URL resolves to the environment root domain.

        Returns:
            bool: True if the URL is the environment root domain, otherwise False.
        """
        if not self.am_request:
            return False
        if not self.parsed_url:
            return False
        return (
            self.parsed_url.netloc == account_settings.environment_account_manager_domain
            and self.parsed_url.path == "/"
        )

    @cached_property
    def is_smarter_api(self) -> bool:
        """
        Returns True if the URL is of the form http://localhost:8000/api/v1/.

        Examples:
            - path_parts: ['api', 'v1', 'chatbots', '1', 'chat']
            - http://api.localhost:8000/

        Returns:
            bool: True if the URL matches the smarter API pattern, otherwise False.
        """
        if not self.am_request:
            return False
        if not self.url:
            return False
        if "api" in self.url_path_parts:
            return True
        return False

    @cached_property
    def is_default_domain(self) -> bool:
        """
        Returns True if the URL is the default domain for the environment.

        Example:
            api.alpha.account.smarter.sh

        :return:
            bool: True if the URL is the default environment domain, otherwise False.
        """
        if not self.am_request:
            return False
        if not self.url:
            return False
        return account_settings.environment_api_domain in self.url

    @cached_property
    def path(self) -> Optional[str]:
        """
        Extracts the path from the URL.

        :return:
            Optional[str]: The path as a string, or None if not found.

        Examples:
            - https://hr.3141-5926-5359.alpha.api.example.com/chatbot/
              returns '/chatbot/'
        """
        if not self.am_request:
            return None
        if not self.url:
            return None
        if not self.parsed_url:
            return None
        if self.parsed_url.path == "":
            return "/"
        return self.parsed_url.path

    @cached_property
    def root_domain(self) -> Optional[str]:
        """
        Extracts the root domain from the URL.

        :return: The root domain or None if not found.

        Example::

            request_mixin = AMRequestMixin(request)
            print(request_mixin.root_domain)
            # For 'https://hr.3141-5926-5359.alpha.api.example.com/chatbot/' → 'smarter.sh'
            # For 'http://localhost:8000/' → 'localhost'

        """
        if not self.am_request:
            return None
        if not self.url:
            return None
        url = AMValidator.urlify(self.url, environment=account_settings.environment)  # type: ignore
        if url:
            extracted = tldextract.extract(url)
            if extracted.domain and extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}"
            if extracted.domain:
                return extracted.domain
        return None

    @cached_property
    def subdomain(self) -> Optional[str]:
        """
        Extracts the subdomain from the URL.

        :return: The subdomain or None if not found.

        Example::

            request_mixin = AMRequestMixin(request)
            sub = request_mixin.subdomain
            print(sub)  # e.g., 'hr.3141-5926-5359.alpha' for
                        # 'https://hr.3141-5926-5359.alpha.api.example.com/chatbot/'
        """
        if not self.am_request:
            return None
        if not self.url:
            return None
        extracted = tldextract.extract(self.url)
        return extracted.subdomain

    @cached_property
    def domain(self) -> Optional[str]:
        """
        Extracts the domain from the URL.

        :return: The domain or None if not found.

        examples::

            - https://hr.3141-5926-5359.alpha.api.example.com/chatbot/
              returns 'hr.3141-5926-5359.alpha.api.example.com'
        """
        if not self.am_request:
            return None
        if not self.parsed_url:
            return None
        return self.parsed_url.netloc if self.parsed_url else None

    @cached_property
    def formatted_class_name(self) -> str:
        """
        Returns the class name in a formatted string
        along with the name of this mixin.

        :return: Formatted class name string.
        """
        parent_class = super().formatted_class_name
        return f"{parent_class}.AMRequestMixin()"

    @cached_property
    def is_requestmixin_ready(self) -> bool:
        """
        Returns True if the request mixin is ready for processing.
        This is a convenience property to check if the request is ready.

        :return: True if the request mixin is ready, False otherwise.
        """
        # cheap and easy way to fail.
        if not isinstance(self._am_request, Union[HttpRequest, RestFrameworkRequest, WSGIRequest, MagicMock]):
            logger.debug(
                "%s.is_requestmixin_ready() - %s request is not a HttpRequest. Received %s. Cannot process request.",
                self.formatted_class_name,
                self._instance_id,
                type(self._am_request).__name__,
            )
            return False
        if not isinstance(self._parse_result, ParseResult):
            logger.debug(
                "%s.is_requestmixin_ready() - %s _parse_result is not a ParseResult. Received %s. Cannot process request.",
                self.formatted_class_name,
                self._instance_id,
                type(self._parse_result).__name__,
            )
            return False
        if not isinstance(self._url, str):
            logger.debug(
                "%s.is_requestmixin_ready() - %s _url is not a string. Received %s. Cannot process request.",
                self.formatted_class_name,
                self._instance_id,
                type(self._url).__name__,
            )
            return False
        return True

    @property
    def ready(self) -> bool:
        """
        returns True if the request is ready for processing.

        :return: True if the request is ready, False otherwise.

        """
        retval = bool(super().ready)
        if not retval:
            logger.debug(
                "%s.ready() - %s super().ready returned False. This might cause problems with other initializations.",
                self.formatted_class_name,
                self._instance_id,
            )
        return retval and self.is_requestmixin_ready

    # --------------------------------------------------------------------------
    # instance methods
    # --------------------------------------------------------------------------
    def get_cookie_value(self, cookie_name):
        """
        Retrieve the value of a cookie from the request object.

        :param request: Django HttpRequest object
        :param cookie_name: Name of the cookie to retrieve
        :return: Value of the cookie or None if the cookie does not exist
        """
        if self.am_request and self.am_request.COOKIES:
            return self.am_request.COOKIES.get(cookie_name)

    def to_json(self) -> dict[str, Any]:
        """
        serializes the object.

        :return: A dictionary representation of the object.
        """
        if not self.is_requestmixin_ready:
            return super().to_json()
        return {
            "ready": self.ready,
            "url": self.url,
            "auth_header": self.auth_header[:10] + "****" if self.auth_header else None,
            "api_token": mask_string(self.api_token.decode()) if self.api_token else None,
            "data": self.data,
            "is_smarter_api": self.is_smarter_api,
            "is_default_domain": self.is_default_domain,
            "path": self.path,
            "root_domain": self.root_domain,
            "subdomain": self.subdomain,
            "domain": self.domain,
            "timestamp": self.timestamp.isoformat(),
            "unique_client_string": self.unique_client_string,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "parsed_url": str(self.parsed_url) if self.parsed_url else None,
            "request": self.am_request is not None,
            "qualified_request": self.qualified_request,
            "url_path_parts": self.url_path_parts,
            "params": self.params,
            "is_environment_root_domain": self.is_environment_root_domain,
            **super().to_json(),
        }

    def helper_logger(self, message: str):
        """
        Create a log entry
        """
        logger.info("%s %s", self.formatted_class_name, message)

    def dump(self):
        """
        Dump the object to the console.
        """
        return json.dumps(self.to_json())
