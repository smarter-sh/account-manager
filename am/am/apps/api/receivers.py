"""Receiver functions for chatapp signals."""

# pylint: disable=W0613


import logging
from typing import Optional, Union

from django.core.handlers.wsgi import WSGIRequest
from django.dispatch import receiver

from am.common.conf import am_settings
from am.common.helpers.console_helpers import formatted_json, formatted_text
from am.lib import json
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .signals import api_request_completed, api_request_initiated


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.RECEIVER_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


# api_request_initiated.send(sender=self.__class__, instance=self, request=request)
@receiver(api_request_initiated, dispatch_uid="api_request_initiated")
def handle_api_request_initiated(sender, instance, request: WSGIRequest, **kwargs):
    """Handle API request initiated signal."""
    logger.info(
        "%s - %s - %s",
        formatted_text("am.apps.api.receivers.api_request_initiated"),
        instance.__class__.__name__,
        request.path,
    )


@receiver(api_request_completed, dispatch_uid="api_request_completed")
def handle_api_request_completed(sender, instance, request: WSGIRequest, response, **kwargs):
    """Handle API request completed signal."""
    json_content: Optional[Union[dict, list, str]]
    try:
        json_content = json.loads(response.content)
    # pylint: disable=W0718
    except Exception:
        logger.warning(
            "handle_api_request_completed: recasting json response.content failed. attempting to decode as utf-8"
        )
        try:
            json_content = response.content.decode("utf-8", errors="replace")
        except Exception:
            json_content = None

    logger.info(
        "%s - %s - %s\n%s",
        formatted_text("am.apps.api.receivers.api_request_completed"),
        instance.__class__.__name__,
        request.path,
        formatted_json(json_content) if isinstance(json_content, dict) else json_content,
    )
