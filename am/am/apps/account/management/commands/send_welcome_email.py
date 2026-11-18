"""This module is used to send the html welcome email to a user in the AccountContact table."""

from typing import Optional

from am.apps.account.models import Account, AccountContact, UserProfile
from am.common.exceptions import AMValueError
from am.lib.django.management.base import AMCommand


# pylint: disable=E1101
class Command(AMCommand):
    """Send the html welcome email to a user in the AccountContact table."""

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument(
            "--account_number", type=str, help="The Account Manager account number to which the user belongs"
        )
        parser.add_argument("--company_name", type=str, help="The company name to which the user belongs")
        parser.add_argument("--username", type=str, help="The username")
        parser.add_argument("--email", type=str, help="The email address")

    def handle(self, *args, **options):
        """Create the superuser account."""
        self.handle_begin()

        account_number = options["account_number"]
        company_name = options["company_name"]
        username = options["username"]
        email = options["email"]

        account: Optional[Account] = None

        if username:
            user_profile = UserProfile.objects.get(user__username=username)
            account = user_profile.account
            email = email or user_profile.user.email
        elif account_number or company_name:
            try:
                account = (
                    Account.objects.get(account_number=account_number)
                    if account_number
                    else Account.objects.get(company_name=company_name)
                )
            except Account.DoesNotExist as e:
                self.handle_completed_failure(e, msg=f"Account {account_number or company_name} not found.")
                return
            if not email:
                raise AMValueError("You must provide an email address with an account number or company name.")
        elif email:
            user_profile = UserProfile.objects.get(user__email=email)
            account = user_profile.account
        else:
            raise AMValueError(
                "You must provide either a username, or an email address with an optional account number or company name."
            )

        account_contact, created = AccountContact.objects.get_or_create(
            account=account,
            email=email,
        )

        # AccountContact.save() already welcomes a new contact.
        if not created:
            account_contact.send_welcome_email()

        self.handle_completed_success()
