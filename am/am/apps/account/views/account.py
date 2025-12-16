# pylint: disable=C0115
"""Django views"""
import logging

from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.view_helpers import AMAuthenticatedNeverCachedWebView
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


# ------------------------------------------------------------------------------
# Protected Views
# ------------------------------------------------------------------------------


class AccountOrganizationView(AMAuthenticatedNeverCachedWebView):

    template_path = "account/organization.html"


class AccountTeamView(AMAuthenticatedNeverCachedWebView):

    template_path = "account/team.html"


class AccountLimitsView(AMAuthenticatedNeverCachedWebView):

    template_path = "account/limits.html"


class AccountProfileView(AMAuthenticatedNeverCachedWebView):

    template_path = "account/profile.html"


class AccountAPIKeysView(AMAuthenticatedNeverCachedWebView):
    """API keys view"""

    template_path = "dashboard/api-keys.html"


class AccountUsageView(AMAuthenticatedNeverCachedWebView):
    """Usage view"""

    template_path = "dashboard/usage.html"
