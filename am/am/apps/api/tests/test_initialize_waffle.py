"""Test the initialize_waffle management command."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from waffle.models import Switch

from am.common.const import AMEnvironments
from am.lib.django.waffle import AMWaffleSwitches

COMMAND_MODULE = "am.apps.api.management.commands.initialize_waffle"


class TestInitializeWaffle(TestCase):
    """Test that initialize_waffle creates the expected switches and deletes the others."""

    def tearDown(self):
        # the transaction is rolled back, but waffle's cache (in Redis) is not: drop
        # whatever this test may have cached for these switches.
        for name in AMWaffleSwitches().all + ["am_test_orphaned_switch"]:
            Switch(name=name).flush()
        super().tearDown()

    def run_command(self, environment: str) -> str:
        """Run the command in ``environment``, and return its output."""
        out = StringIO()
        with patch(f"{COMMAND_MODULE}.am_settings") as mock_settings:
            mock_settings.environment = environment
            call_command("initialize_waffle", stdout=out)
        return out.getvalue()

    def test_creates_switches_and_deletes_orphans(self):
        """Missing switches are created off, and switches nobody defines are deleted."""
        Switch.objects.all().delete()
        Switch.objects.create(name="am_test_orphaned_switch", active=True)
        existing = AMWaffleSwitches().all[0]
        Switch.objects.create(name=existing, active=True)

        output = self.run_command(AMEnvironments.PROD)

        self.assertEqual(set(Switch.objects.values_list("name", flat=True)), set(AMWaffleSwitches().all))
        self.assertFalse(Switch.objects.filter(name="am_test_orphaned_switch").exists())
        self.assertIn("Deleting orphaned switch am_test_orphaned_switch", output)
        self.assertTrue(Switch.objects.get(name=existing).active)
        others = Switch.objects.exclude(name=existing)
        self.assertFalse(others.filter(active=True).exists())

    def test_local_environment_turns_on_reactapp_debug_mode(self):
        """In a local environment, REACTAPP_DEBUG_MODE is turned on."""
        Switch.objects.all().delete()
        self.run_command(AMEnvironments.LOCAL)
        self.assertTrue(Switch.objects.get(name=AMWaffleSwitches.REACTAPP_DEBUG_MODE).active)
