"""Register a Smarter platform that may call the subscription status api, or rotate its key."""

from am.apps.account.models import PlatformClient
from am.lib.django.management.base import AMCommand


class Command(AMCommand):
    """
    Django manage.py create_platform_api_key command.

    Registers a multitenant Smarter platform by its host, e.g. ``alpha.platform.example.com``, and
    prints its new key once. With ``--rotate``, it replaces the key of a platform that is already
    registered; the old key stops working at once. The platform sends the key as
    ``Authorization: Platform <key>`` (Smarter's ``SMARTER_ACCOUNT_MANAGER_API_KEY`` setting).

    This is an operator's command. Never run it from a deployment job: the key belongs in a
    secret, not in a job log.
    """

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument("--host", type=str, required=True, help="The platform's host name")
        parser.add_argument("--description", type=str, help="Optional brief text description of the platform")
        parser.add_argument("--rotate", action="store_true", help="Replace the key of a registered platform")

    def handle(self, *args, **options):
        """Register the platform, or rotate its key, and print the key."""
        self.handle_begin()
        host = options["host"].strip().lower()
        client = PlatformClient.objects.filter(host_name=host).first()

        if options["rotate"]:
            if client is None:
                self.handle_completed_failure(msg=f"Platform {host} is not registered")
                return
            key = client.rotate_key()
            self.handle_completed_success(msg=f"Rotated the API key of platform {host}")
        else:
            if client is not None:
                self.handle_completed_failure(msg=f"Platform {host} is already registered. Use --rotate for a new key.")
                return
            client, key = PlatformClient.create_with_key(host, description=options["description"])
            self.handle_completed_success(msg=f"Registered platform {client.host_name}")

        self.stdout.write(self.style.SUCCESS("*" * 80))
        self.stdout.write(self.style.SUCCESS(f"Platform API key: {key}"))
        self.stdout.write(self.style.SUCCESS("*" * 80))
        self.stdout.write(
            self.style.WARNING(
                "This key is only displayed once and cannot be recovered if lost. Store it as the platform's "
                "SMARTER_ACCOUNT_MANAGER_API_KEY secret."
            )
        )
