"""Enumerations for account-related choices."""

from enum import IntEnum


class AMHostingPlanTypeEnum(IntEnum):
    """
    Enumeration for hosting plan types.

    An ``IntEnum``, because :attr:`am.apps.account.models.Subscription.plan_type` is an
    ``IntegerField`` whose choices and default are these members: Django saves them, and
    compares them with the integers it reads back, only if they are ints.
    """

    MULTITENANT = 1
    HOSTED_PLATFORM = 2
    MANAGED_PLATFORM = 3
