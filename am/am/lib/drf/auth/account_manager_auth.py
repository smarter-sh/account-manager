from rest_framework.authentication import BaseAuthentication

from am.apps.account.models import Account
from am.apps.account.utils import get_cached_admin_user_for_account


class AMAuthentication(BaseAuthentication):
    """
    Custom authentication class for Account Manager.
    This class can be extended to implement specific authentication logic.

    This is used to verify the payment status of the account associated with the
    host of the incoming request. for our three hosting plans, this is:

    mutlitenant: account number passed as request.headers.get("X-API-KEY")
    hosted platform: the domain name of the request
    managed platform: the domain name of the request
    """

    def authenticate(self, request):
        # Implement custom authentication logic here
        token = request.headers.get("X-API-KEY")
        if not token:
            return None  # No authentication attempted

        try:
            account = Account.objects.get(account_number=token)
            user = get_cached_admin_user_for_account(account)
            return (user, token)
        except Account.DoesNotExist:
            return None  # X-API-KEY does not contain a valid account number
