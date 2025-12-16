# pylint: disable=unused-argument
"""Django signal receivers for account app."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from am.common.conf import am_settings
from am.common.helpers.console_helpers import formatted_text
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .models import AMAuthToken
from .signals import (
    smarter_token_authentication_failure,
    smarter_token_authentication_request,
    smarter_token_authentication_success,
)


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.RECEIVER_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)
module_prefix = "am.lib.drf.receivers"


@receiver(post_save, sender=AMAuthToken)
def smarter_auth_token_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of AMAuthToken model."""
    if created:
        logger.info(
            "%s.%s AMAuthToken post_save signal received. instance: %s, created: %s",
            module_prefix,
            formatted_text("smarter_auth_token_save()"),
            instance,
            created,
        )
    else:
        logger.info(
            "%s.%s AMAuthToken post_save signal received. instance: %s, created: %s",
            module_prefix,
            formatted_text("smarter_auth_token_save()"),
            instance,
            created,
        )


@receiver(post_delete, sender=AMAuthToken)
def smarter_auth_token_delete(sender, instance, **kwargs):
    """Signal receiver for deleted of AMAuthToken model."""
    logger.info(
        "%s.%s AMAuthToken post_delete signal received. instance: %s",
        module_prefix,
        formatted_text("smarter_auth_token_delete()"),
        instance,
    )


@receiver(smarter_token_authentication_request)
def authentication_request_receiver(sender, token, **kwargs):
    """Signal receiver for authentication request."""
    logger.info(
        "%s signal received. sender: %s, token: %s",
        formatted_text(f"{module_prefix}.smarter_token_authentication_request()"),
        sender,
        token,
    )


@receiver(smarter_token_authentication_success)
def authorization_granted_receiver(sender, user, token, **kwargs):
    """Signal receiver for authorization granted."""
    logger.info(
        "%s signal received. sender: %s, user: %s, token: %s",
        formatted_text(f"{module_prefix}.smarter_token_authentication_success()"),
        sender,
        user,
        token,
    )


@receiver(smarter_token_authentication_failure)
def authorization_denied_receiver(sender, user, token, **kwargs):
    """Signal receiver for authorization denied."""
    logger.info(
        "%s signal received. sender: %s, user: %s, token: %s",
        formatted_text(f"{module_prefix}.smarter_token_authentication_failure()"),
        sender,
        user,
        token,
    )
