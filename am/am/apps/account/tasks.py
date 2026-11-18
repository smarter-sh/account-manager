# pylint: disable=W0613,C0115,R0913
"""
Celery tasks for account app.

These tasks are i/o intensive operations for creating billing records with
Celery workers in order to avoid blocking the main app thread. This is advance work to lay groundwork for
future high-traffic scenarios.
"""

# python stuff
import logging

# django stuff
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Sum

from am.common.conf import am_settings
from am.common.helpers.console_helpers import formatted_text
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

# Account Manager stuff
from am.workers.celery import app

# Account stuff
from .models import Charge, DailyBillingRecord


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return (
        waffle.switch_is_active(AMWaffleSwitches.TASK_LOGGING)
        and waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING)
        and level >= am_settings.log_level
    )


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)
module_prefix = "am.apps.account.tasks."


@app.task(
    autoretry_for=(Exception,),
)
def aggregate_charges():
    """
    Top-level Celery task for aggregating charge records.

    This task triggers the aggregation of daily billing records by calling
    :func:`aggregate_daily_billing_records`. It is typically scheduled via Celery Beat.

    **Example usage**::

        # Trigger aggregation from code
        aggregate_charges.delay()

        # Schedule with Celery Beat for daily aggregation
        # (see your Celery Beat configuration)
    """

    prefix = formatted_text(module_prefix + "aggregate_charges()")
    logger.info(prefix)
    aggregate_daily_billing_records()


@app.task(
    autoretry_for=(Exception,),
)
def aggregate_daily_billing_records():
    """
    Aggregate daily billing records and delete individual Charge records.

    This Celery task is typically scheduled via Celery Beat and is designed to be idempotent,
    meaning it can be safely run multiple times without causing duplicate records.

    .. note::

           - This task aggregates all charges for each user/account/date/provider/charge_type combination,
           - updates or creates a corresponding DailyBillingRecord, and deletes the original Charge records.

    **Example usage**::

        # Trigger aggregation from code
        aggregate_daily_billing_records.delay()

        # Schedule with Celery Beat for daily aggregation
        # (see your Celery Beat configuration)
    """
    MAX_AGGREGATION_ERROR_THRESHOLD = 10
    message_prefix = formatted_text(module_prefix + "aggregate_daily_billing_records()")

    def aggregate(user, account, created_at_date, provider, charge_type):
        """Handle aggregation of one set of charges."""
        with transaction.atomic():
            aggregation_queryset = Charge.objects.filter(
                user=user,
                account=account,
                created_at__date=created_at_date,
                provider=provider,
                charge_type=charge_type,
            )

            aggregated_data = aggregation_queryset.aggregate(
                prompt_tokens=Sum("prompt_tokens"),
                completion_tokens=Sum("completion_tokens"),
                total_tokens=Sum("total_tokens"),
            )

            try:
                record = DailyBillingRecord.objects.get(
                    user_id=user, account_id=account, date=created_at_date, provider=provider, charge_type=charge_type
                )
                record.prompt_tokens += aggregated_data["prompt_tokens"]
                record.completion_tokens += aggregated_data["completion_tokens"]
                record.total_tokens += aggregated_data["total_tokens"]
                record.save()
            except DailyBillingRecord.DoesNotExist:
                DailyBillingRecord.objects.create(
                    user_id=user,
                    account_id=account,
                    date=created_at_date,
                    provider=provider,
                    charge_type=charge_type,
                    prompt_tokens=aggregated_data["prompt_tokens"],
                    completion_tokens=aggregated_data["completion_tokens"],
                    total_tokens=aggregated_data["total_tokens"],
                )

            aggregation_queryset.delete()

    logger.info("%s - begin.", message_prefix)
    i = 0
    i_error_count = 0

    working_queryset = Charge.objects.values(
        "user", "account", "created_at__date", "provider", "charge_type"
    ).distinct()
    logger.info("%s found %s pending billing items", message_prefix, working_queryset.count())

    for charge_identity in working_queryset:
        user = charge_identity["user"]
        account = charge_identity["account"]
        created_at_date = charge_identity["created_at__date"]
        provider = charge_identity["provider"]
        charge_type = charge_identity["charge_type"]

        try:
            aggregate(user, account, created_at_date, provider, charge_type)
        except (DatabaseError, IntegrityError) as e:
            logger.error("%s - error processing billing item %s: %s", message_prefix, charge_identity, e)
            i_error_count += 1
            if i_error_count >= MAX_AGGREGATION_ERROR_THRESHOLD:
                logger.error("%s - exceeded error threshold, aborting.", message_prefix)
                break
        # pylint: disable=W0718
        except Exception as e:
            logger.error("%s - unknown error processing billing item %s: %s", message_prefix, charge_identity, e)
            i_error_count += 1
            if i_error_count >= MAX_AGGREGATION_ERROR_THRESHOLD:
                logger.error("%s - exceeded error threshold, aborting.", message_prefix)
                break

        i += 1
        if i % 100 == 0:
            logger.info("%s processed %s billing items", message_prefix, i)

    logger.info("%s - finished.", message_prefix)
