"""This module is used to create a new account."""

from django.contrib.sites.models import Site

from am.common.conf import am_settings
from am.lib.django.management.base import AMCommand


# pylint: disable=E1101
class Command(AMCommand):
    """Initialize Django Oscar site"""

    def handle(self, *args, **options):
        """Initialize the Django Oscar site."""
        self.handle_begin()
        Site.objects.update_or_create(
            id=1, defaults={"domain": am_settings.environment_domain, "name": am_settings.environment_domain}
        )
        Site.objects.update_or_create(
            id=2, defaults={"domain": am_settings.environment_api_domain, "name": am_settings.environment_api_domain}
        )
        self.handle_completed_success()
