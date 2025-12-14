# pylint: disable=unused-argument
"""Django signal receivers for account app."""

import logging

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict

from account.common.conf import account_settings
from account.common.helpers.console_helpers import formatted_text
from account.lib import json
from account.lib.django import waffle
from account.lib.django.waffle import AMWaffleSwitches
from account.lib.logging import WaffleSwitchedLoggerWrapper

from .models import Account, Charge, DailyBillingRecord, User, UserProfile
from .utils import cache_invalidate, get_cached_default_account, get_cached_user_profile


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.RECEIVER_LOGGING) and level >= account_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


module_prefix = "account.apps.account.receivers"


@receiver(user_logged_in)
def user_logged_in_receiver(sender, request, user, **kwargs):
    """
    Signal receiver for user login.
    - verify that a UserProfile record exists for the user.
      if not, create one with the default account.
    """
    logger.info(
        "%s User logged in signal received. user: %s", formatted_text(f"{module_prefix}.user_logged_in()"), user
    )
    if not get_cached_user_profile(user=user):
        logger.warning("User profile not found for user: %s", user)
        account = get_cached_default_account()
        UserProfile.objects.create(user=user, account=account)


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of User model."""
    logger.info(
        "%s User post_save signal received. instance: %s, created: %s",
        formatted_text(f"{module_prefix}.user_post_save()"),
        instance,
        created,
    )
    if not created:
        cache_invalidate(user=instance)


@receiver(post_delete, sender=User)
def user_post_delete(sender, instance, **kwargs):
    """Signal receiver for deleted of User model."""
    logger.info(
        "%s User post_delete signal received. instance: %s, id: %s",
        formatted_text(f"{module_prefix}.user_post_delete()"),
        instance,
        instance.id,
    )


@receiver(post_save, sender=UserProfile)
def user_profile_post_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of UserProfile model."""
    logger.info(
        "%s UserProfile post_save signal received. instance: %s, created: %s",
        formatted_text(f"{module_prefix}.user_profile_post_save()"),
        instance,
        created,
    )
    if not created:
        cache_invalidate(user=instance.user, account=instance.account)


@receiver(post_delete, sender=UserProfile)
def user_profile_post_delete(sender, instance, **kwargs):
    """Signal receiver for deleted of UserProfile model."""
    logger.info(
        "%s UserProfile post_delete signal received. instance: %s, id: %s",
        formatted_text(f"{module_prefix}.user_profile_post_delete()"),
        instance,
        instance.id,
    )


@receiver(post_save, sender=Account)
def account_post_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of Account model."""
    model_prefix = formatted_text(f"{module_prefix}.account_post_save() signal received.")
    account_json = json.dumps(model_to_dict(instance))
    if created:
        logger.info("%s Account created: %s", model_prefix, instance)
    else:
        cache_invalidate(account=instance)

    logger.info("%s instance: %s", model_prefix, account_json)


@receiver(post_delete, sender=Account)
def account_post_delete(sender, instance, **kwargs):
    """Signal receiver for deleted of Account model."""
    logger.info(
        "%s Account post_delete signal received. instance: %s, id: %s",
        formatted_text(f"{module_prefix}.account_post_delete()"),
        instance,
        instance.id,
    )


@receiver(post_save, sender=Charge)
def charge_post_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of Charge model."""
    charge_json = json.dumps(model_to_dict(instance))
    logger.info(
        "%s Charge post_save signal received. instance: %s, created: %s",
        formatted_text(f"{module_prefix}.charge_post_save()"),
        charge_json,
        created,
    )


@receiver(post_save, sender=DailyBillingRecord)
def daily_billing_record_post_save(sender, instance, created, **kwargs):
    """Signal receiver for created/saved of DailyBillingRecord model."""
    daily_billing_record_json = json.dumps(model_to_dict(instance))
    logger.info(
        "%s DailyBillingRecord post_save signal received. instance: %s, created: %s",
        formatted_text(f"{module_prefix}.daily_billing_record_post_save()"),
        daily_billing_record_json,
        created,
    )
