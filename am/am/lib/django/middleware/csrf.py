"""
This module contains the SmarterCsrfViewMiddleware class, a subclass of Django's.

CsrfViewMiddleware that skips health checks and internal hosts, and skips CSRF
checks in the local environment.
"""

import logging

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError
from django.middleware.csrf import CsrfViewMiddleware

from am.common.classes import AMHelperMixin
from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.MIDDLEWARE_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class SmarterCsrfViewMiddleware(CsrfViewMiddleware, AMHelperMixin):
    """
    Django's CSRF middleware, with short-circuits for health checks, internal hosts and local development.

    - Health checks (the amnesty urls) and requests addressed to an internal IP host
      (``settings.ACCOUNT_INTERNAL_IP_PREFIXES``) get no CSRF cookie set up.
    - In the local environment, :meth:`process_view` skips the CSRF check.
    - Otherwise Django's ``CsrfViewMiddleware`` does the work, with ``settings.CSRF_TRUSTED_ORIGINS``.

    **Example**

    To enable this middleware, add it to your Django project's middleware settings::

        MIDDLEWARE = [
            ...
            'am.lib.django.middleware.csrf.SmarterCsrfViewMiddleware',
            ...
        ]
    """

    def process_request(self, request):
        """
        Set up CSRF protection for the request.

        Health checks and requests addressed to an internal IP host are passed through
        without a CSRF cookie. The middleware never changes ``request.user``.

        :param request: The incoming request.
        :returns: A 500 response if the host can't be parsed, otherwise None.
        """
        host = request.get_host()
        if not host:
            return HttpResponseServerError("Internal error (500) - could not parse request.")

        # Short-circuit for health checks
        if request.path.replace("/", "") in self.amnesty_urls:
            return None

        # Short-circuit for any requests born from internal IP address hosts.
        # This is unlikely, but not impossible.
        if any(host.startswith(prefix) for prefix in settings.ACCOUNT_INTERNAL_IP_PREFIXES):
            logger.info(
                "%s %s identified as an internal IP address, exiting.",
                self.formatted_class_name,
                self.smarter_build_absolute_uri(request),
            )
            return None

        logger.info("%s.process_request(): %s", self.formatted_class_name, self.smarter_build_absolute_uri(request))
        return super().process_request(request)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        """
        Check the request's CSRF token, except in the local environment.

        :param request: The incoming request.
        :param callback: The view function.
        :param callback_args: The view's positional arguments.
        :param callback_kwargs: The view's keyword arguments.
        :returns: None to accept the request, or Django's 403 response.
        """
        if am_settings.environment == "local":
            logger.debug("%s._accept: environment is local. ignoring csrf checks", self.formatted_class_name)
            return None
        response = super().process_view(request, callback, callback_args, callback_kwargs)
        if isinstance(response, HttpResponseForbidden):
            logger.error("%s CSRF validation failed", self.formatted_class_name)
        return response
