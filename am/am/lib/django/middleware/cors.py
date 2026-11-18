"""This module contains the middleware for handling CORS headers for the application."""

import logging
from collections.abc import Awaitable

from corsheaders.middleware import CorsMiddleware
from django.conf import settings
from django.http import HttpRequest, HttpResponseServerError
from django.http.response import HttpResponseBase

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


class SmarterCorsMiddleware(CorsMiddleware, AMHelperMixin):
    """
    Django-cors-headers' ``CorsMiddleware``, with a guard for unparsable requests and logging.

    The allowed origins are those of ``settings.CORS_ALLOWED_ORIGINS`` and
    ``settings.CORS_ALLOWED_ORIGIN_REGEXES``, exactly as in ``CorsMiddleware``.

    - A request whose host can't be determined gets a 500 response.
    - Health checks (the amnesty urls) and requests addressed to an internal IP host
      (``settings.ACCOUNT_INTERNAL_IP_PREFIXES``) go straight to ``CorsMiddleware``.

    **Example**

    To enable this middleware, add it to your Django project's middleware settings::

        MIDDLEWARE = [
            ...
            'am.lib.django.middleware.cors.SmarterCorsMiddleware',
            ...
        ]
    """

    def __call__(self, request: HttpRequest) -> HttpResponseBase | Awaitable[HttpResponseBase]:
        """
        Add CORS headers to the response.

        :param request: The incoming request.
        :returns: The response, with CORS headers where they apply, or a 500 response if the host is empty.
        """
        host = request.get_host()
        if not host:
            return HttpResponseServerError("Internal error (500) - could not parse request.")

        # Short-circuit for health checks
        if request.path.replace("/", "") in self.amnesty_urls:
            return super().__call__(request)

        # Short-circuit for any requests born from internal IP address hosts
        if any(host.startswith(prefix) for prefix in settings.ACCOUNT_INTERNAL_IP_PREFIXES):
            logger.info(
                "%s %s identified as an internal IP address, exiting.",
                self.formatted_class_name,
                self.smarter_build_absolute_uri(request),
            )
            return super().__call__(request)

        logger.info("%s.__call__() - url=%s", self.formatted_class_name, self.smarter_build_absolute_uri(request))
        return super().__call__(request)
