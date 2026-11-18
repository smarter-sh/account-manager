"""This module is used to print every Django setting to the console."""

from django.conf import settings

from am.lib.django.management.base import AMCommand


# pylint: disable=E1101
class Command(AMCommand):
    """Print every upper-case Django setting to the console."""

    def handle(self, *args, **options):
        """Dump all Django settings."""
        self.handle_begin()

        for setting in dir(settings):
            if setting.isupper():
                self.stdout.write(f"{setting}: {getattr(settings, setting)}")

        self.handle_completed_success()
