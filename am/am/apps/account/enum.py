"""
Enumerations for account-related choices.
"""

from am.common.enum import AMEnumAbstract


class AMHostingPlanTypeEnum(AMEnumAbstract):
    """Enumeration for hosting plan types."""

    MULTITENANT = 1
    HOSTED_PLATFORM = 2
    MANAGED_PLATFORM = 3
