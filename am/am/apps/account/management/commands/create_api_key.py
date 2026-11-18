"""This module is used to create a new api key."""

from am.apps.account.models import Account, User, UserProfile
from am.apps.account.utils import get_cached_admin_user_for_account
from am.lib.django.management.base import AMCommand
from am.lib.drf.models import AMAuthToken


# pylint: disable=E1101
class Command(AMCommand):
    """Django manage.py create_api_key command.

    This command is used to create a new api key for an account user.
    """

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument(
            "--account_number",
            type=str,
            help="The Smarter account number to which the user belongs. Format: ####-####-####",
        )
        parser.add_argument("--username", type=str, help="The username of the api key owner")
        parser.add_argument("--description", type=str, help="Optional brief text description for the api key")

    def handle(self, *args, **options):
        """Create the superuser account."""
        self.handle_begin()

        account: Account | None = None
        user: User | None = None
        user_profile: UserProfile | None = None
        account_number = options["account_number"]
        username = options["username"]
        description = options["description"]

        if not account_number and not username:
            self.handle_completed_failure(msg="You must provide an account number or a username")
            return

        if account_number:
            account = Account.objects.get(account_number=account_number)
            user = get_cached_admin_user_for_account(account)
        if username:
            user = User.objects.get(username=username)
            user_profile = (
                UserProfile.objects.get(user=user, account=account)
                if account
                else UserProfile.objects.filter(user=user).first()
            )
            if not user_profile:
                self.handle_completed_failure(msg=f"User {username} does not have a user profile")
                return
            account = user_profile.account

        # raises UserProfile.DoesNotExist if the user does not belong to the account
        owner = UserProfile.objects.get(user=user, account=account)
        account_number = owner.account.account_number
        username = owner.user.username

        auth_token, token_key = AMAuthToken.objects.create(
            name=f"{account_number}.{username}", user=owner.user, description=description
        )  # type: ignore[assignment]
        self.handle_completed_success(
            msg=f"Created API key {auth_token.name} for account {account_number} and user {username}"
        )
        self.stdout.write(self.style.SUCCESS("*" * 80))
        self.stdout.write(self.style.SUCCESS(f"API key: {token_key}"))
        self.stdout.write(self.style.SUCCESS("*" * 80))
        self.stdout.write(
            self.style.WARNING(
                "This API key is only displayed once and cannot be recovered if lost. Store it in a secure location."
            )
        )
