"""This module is used to create a superuser account."""

import secrets
import string

from am.apps.account.models import Account, AccountContact, User, UserProfile
from am.common.const import (
    ACCOUNT_ACCOUNT_NUMBER,
    ACCOUNT_COMPANY_NAME,
    ACCOUNT_CUSTOMER_SUPPORT_EMAIL,
    ACCOUNT_CUSTOMER_SUPPORT_PHONE,
)
from am.lib.django.management.base import AMCommand
from am.lib.drf.models import AMAuthToken


# pylint: disable=E1101
class Command(AMCommand):
    """Create a new Account Manager superuser."""

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument("-u", "--username", type=str, help="The username for the new superuser")
        parser.add_argument("-e", "--email", type=str, help="The email address for the new superuser")
        parser.add_argument("-p", "--password", type=str, help="The password for the new superuser")

    def handle(self, *args, **options):
        """Create the superuser account."""
        self.handle_begin()

        username = options["username"]
        email = options["email"]
        password = options["password"]

        account, created = Account.objects.get_or_create(
            account_number=ACCOUNT_ACCOUNT_NUMBER,
            company_name=ACCOUNT_COMPANY_NAME,
        )
        account.is_default_account = True
        account.phone_number = "+1 (617) 834-6172"
        account.address1 = "851 Burlway Road"
        account.address2 = "Suite 101"
        account.city = "Burlingame"
        account.state = "CA"
        account.postal_code = "94010"
        account.country = "USA"
        account.timezone = "America/Los_Angeles"
        account.currency = "USD"
        account.save()

        if created:
            self.handle_completed_success(msg=f"Created account: {account.account_number} {account.company_name}")

        user, created = User.objects.get_or_create(
            username=username, email=email, is_superuser=True, is_staff=True, is_active=True
        )
        if created:
            if not password:
                password_length = 16
                alphabet = string.ascii_letters + string.digits + string.punctuation
                password = "".join(secrets.choice(alphabet) for _ in range(password_length))

            user.set_password(password)
            user.save()

            self.handle_completed_success(msg=f"Created superuser {username} {email} has been created.")
        else:
            self.handle_completed_success(msg=f"User {username} updated.")
        user_profile, created = UserProfile.objects.get_or_create(user=user, account=account)
        if created:
            self.handle_completed_success(
                msg=f"Created user profile for {user_profile.user.username} {user_profile.user.email}, account {user_profile.account.account_number} {user_profile.account.company_name}"
            )

        try:
            account_contact = AccountContact.objects.get(
                account=account,
                is_primary=True,
            )
        except AccountContact.DoesNotExist:
            account_contact = AccountContact(
                account=account,
                first_name="Account",
                last_name="Manager",
                email=ACCOUNT_CUSTOMER_SUPPORT_EMAIL,
                phone=ACCOUNT_CUSTOMER_SUPPORT_PHONE,
                is_primary=True,
                # the contact is our own support inbox, so don't send it a welcome email
                welcomed=True,
            )
            account_contact.save()
            self.handle_completed_success(
                msg=f"Created account contact for {account_contact.first_name} {account_contact.last_name}, account {account_contact.account.account_number} {account_contact.account.company_name}"
            )

        # ensure that the admin user has at least one auth token (api key)
        if not AMAuthToken.objects.filter(user=user).exists():
            auth_token, _ = AMAuthToken.objects.create(
                name="account-admin-key", user=user, description="created by manage.py"
            )  # type: ignore[assignment]
            # this command runs in the deployment's init job, whose log is retained, so never print the key itself.
            self.handle_completed_success(msg=f"created API key {auth_token.name} with key_id: {auth_token.key_id}")
            return
        self.handle_completed_success()
