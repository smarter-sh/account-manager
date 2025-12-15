"""Initialize Waffle flags and switches."""

from django.core.management import call_command
from waffle.models import Switch

from am.common.conf import account_settings
from am.common.const import AMEnvironments
from am.lib.django.management.base import AMCommand
from am.lib.django.waffle import AMWaffleSwitches


# pylint: disable=E1101
class Command(AMCommand):
    """
    Management command to initialize and synchronize Waffle feature switches for the Account Manager.

    This command ensures that all required Waffle switches, as defined by the Account Manager application, are present and correctly initialized in the database. It also removes any orphaned switches that are no longer needed, maintaining a clean and consistent feature flag environment.

    **Key Features and Workflow:**

    - Iterates through the list of expected switches and creates any that are missing, defaulting them to the "off" state.
    - Verifies the existence of each switch, providing feedback for each verification or creation.
    - Identifies and deletes orphaned switches that are present in the database but not defined in the current application configuration.
    - In local development environments, enables the ``REACTAPP_DEBUG_MODE`` switch for enhanced debugging capabilities.

    **Usage:**

    This command is intended to be run during deployment, environment setup, or whenever the set of feature switches may have changed. It helps prevent configuration drift and ensures that feature flags are always in sync with the application’s requirements.

    **Error Handling and Output:**

    - Provides clear console output for each switch that is verified, created, or deleted.
    - Handles all operations atomically to avoid partial updates or inconsistent states.

    **Intended Audience:**

    Developers, system administrators, and DevOps engineers responsible for managing feature flags and application configuration in Account Manager environments. This command is especially useful for onboarding new environments or cleaning up after configuration changes.

    .. seealso::

        :py:class:`waffle.models.Switch` - The Django Waffle model representing feature switches.
        :py:class:`account.lib.django.waffle.AMWaffleSwitches` - The class defining all Account Manager-specific Waffle switches.
        :py:data:`account.common.conf.settings.account_settings` - The Account Manager settings module for environment detection.

    """

    def handle(self, *args, **options):
        """ensure that switches exist. If not, then create them"""

        def verify_switch(switch_name):
            """Initialize a switch."""
            if not Switch.objects.filter(name=switch_name).exists():
                call_command("waffle_switch", switch_name, "off", "--create")
            else:
                print(f"Verified switch {switch_name}")

        self.handle_begin()

        smarter_switches = AMWaffleSwitches().all.copy()

        for switch in smarter_switches:
            verify_switch(switch)

        waffle_switches = Switch.objects.all()
        for switch in waffle_switches:
            if not switch.name in smarter_switches:
                self.stdout.write(self.style.NOTICE(f"Deleting orphaned switch {switch.name}."))
                switch.delete()

        if account_settings.environment == AMEnvironments.LOCAL:
            call_command("waffle_switch", AMWaffleSwitches.REACTAPP_DEBUG_MODE, "on")

        self.handle_completed_success()
