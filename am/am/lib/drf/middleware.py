"""
Authenticate requests via AMTokenAuthentication, a subclass of.

knox.auth TokenAuthentication tokens.
"""

import logging
from datetime import timedelta
from http import HTTPStatus
from typing import Optional

from django.contrib.auth import login
from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from knox.settings import knox_settings
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from am.common.classes import AMHelperMixin
from am.common.conf import am_settings
from am.common.utils import mask_string
from am.lib.django import waffle
from am.lib.django.validators import AMValidator
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .token_authentication import AMTokenAuthentication


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.MIDDLEWARE_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class AMTokenAuthenticationMiddleware(MiddlewareMixin, AMHelperMixin):
    """Middleware to authenticate api requests via AMTokenAuthentication, a subclass of.

    knox.auth TokenAuthentication.

    Does the following, for requests to an Account Manager api url that carry an
    ``Authorization: Token <key>`` header and that no other middleware has authenticated:

    - authenticates the token with :class:`AMTokenAuthentication`, and logs the user in.
    - (via AMTokenAuthentication) sends Django signals for token authentication events.
    - logs a warning when the token is older than ``am_settings.smarter_api_key_max_lifetime_days``.
    - answers ``401 Unauthorized`` (json) when the token doesn't authenticate.

    The middleware keeps no per-request state on the instance, which Django shares between requests.
    """

    @staticmethod
    def get_token(request) -> Optional[str]:
        """Return the knox token from the request's Authorization header.

        :param request: The incoming HTTP request.
        :returns: The token, or None if the header is missing or is for another authentication scheme.
        """
        # auth=['Token', 'd9d56ff4-- A 64-CHARACTER TOKEN --c8176']
        auth = [a.decode() if isinstance(a, bytes) else a for a in get_authorization_header(request).split()]
        prefix = knox_settings.AUTH_HEADER_PREFIX
        if isinstance(prefix, bytes):
            prefix = prefix.decode()
        if len(auth) != 2 or auth[0].lower() != prefix.lower():
            return None
        return auth[1]

    def __call__(self, request, *args, **kwargs):
        """Try to authenticate the request using AMTokenAuthentication.

        :param request: The incoming HTTP request.
        :returns: The response of the next middleware or view, or a 401 response if the token is refused.
        """
        # this is the earliest point at which we can evaluate the request URL.
        url = self.smarter_build_absolute_uri(request)
        if not AMValidator.is_api_endpoint(url):
            return self.get_response(request)

        token = self.get_token(request)
        if token is None:
            # we're not using token authentication, no need to do anything
            return self.get_response(request)
        if getattr(request, "auth", None) is not None:
            # we've already authenticated the request
            # with some other middleware, no need to do anything
            return self.get_response(request)

        # AMTokenAuthentication sends the request, success and failure signals.
        masked_token = mask_string(string=token)
        try:
            result = AMTokenAuthentication().authenticate(request)
        except AuthenticationFailed:
            result = None
        if not result:
            logger.warning("%s token authentication failed for token %s", self.formatted_class_name, masked_token)
            return JsonResponse({"detail": "Authentication failed."}, status=HTTPStatus.UNAUTHORIZED)

        user, auth_token = result
        request.user = user
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        self.warn_if_expired(auth_token, user)
        logger.info("%s authenticated user %s", self.formatted_class_name, user)
        return self.get_response(request)

    def warn_if_expired(self, auth_token, user) -> bool:
        """Log a warning if the token is older than the maximum api key lifetime.

        :param auth_token: The authenticated :class:`AMAuthToken`.
        :param user: The authenticated user.
        :returns: True if the token has exceeded its maximum lifetime.
        """
        max_days = am_settings.smarter_api_key_max_lifetime_days
        if auth_token.created < timezone.now() - timedelta(days=max_days):
            logger.warning(
                "%s token for user %s has exceeded max lifetime of %d days", self.formatted_class_name, user, max_days
            )
            return True
        return False
