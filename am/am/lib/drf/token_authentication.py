"""Knox TokenAuthentication subclass that checks if the token is active."""

import logging

from django.utils import timezone
from knox.auth import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from am.apps.account.models import User
from am.common.classes import AMHelperMixin
from am.common.conf import am_settings
from am.common.utils import mask_string
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .models import AMAuthToken
from .signals import (
    smarter_token_authentication_failure,
    smarter_token_authentication_request,
    smarter_token_authentication_success,
)


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.API_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class AMTokenAuthentication(TokenAuthentication, AMHelperMixin):
    """Enhanced Django Rest Framework (DRF) knox TokenAuthentication.

    This subclass adds:

    - adds an activation field to enable/disable tokens
    - adds Django signals for token authentication events
    - adds app logging
    - verifies token activity.
    - adds timestamp update on token use

    Raises:
        AuthenticationFailed: for any failure to authenticate the token the request.
    """

    model = AMAuthToken

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(
            "%s.__init__() called args: %s, kwargs: %s",
            self.formatted_class_name,
            args,
            kwargs,
        )

    def authenticate_credentials(self, token: bytes) -> tuple[User, AMAuthToken]:
        """Override parent authenticate_credentials() to add token activity check and logging.

        Args:
            token (bytes): The authentication token provided in the request.

        Raises:
            AuthenticationFailed: for any failure to authenticate the token the request.
            AuthenticationFailed: _if the token is not active.
            AuthenticationFailed: if the token is not a bytes instance.

        Returns:
            tuple[User, AMAuthToken]: A tuple containing the authenticated User and AMAuthToken.
        """
        if not isinstance(token, bytes):
            raise AuthenticationFailed("Invalid token type. Expected bytes")
        masked_token = mask_string(string=token.decode())
        smarter_token_authentication_request.send(
            sender=self.__class__,
            token=masked_token,
        )
        logger.info("%s.authenticate_credentials() - %s", self.formatted_class_name, masked_token)
        try:
            user, auth_token = super().authenticate_credentials(token)
        except AuthenticationFailed as e:
            smarter_token_authentication_failure.send(
                sender=self.__class__,
                user=None,
                token=masked_token,
            )
            logger.warning(
                "%s.authenticate_credentials() - failed to authenticate token: %s, error: %s",
                self.formatted_class_name,
                masked_token,
                str(e),
            )
            raise
        if not isinstance(user, User):
            logger.warning(
                "%s.authenticate_credentials() - failed to retrieve user for token: %s",
                self.formatted_class_name,
                masked_token,
            )
            raise AuthenticationFailed("Invalid token")

        # next, we need to ensure that the token is active, otherwise
        # we should raise an exception that exactly matches the one
        # raised by the default token authentication
        smarter_auth_token = AMAuthToken.objects.get(token_key=auth_token.token_key)
        if not smarter_auth_token.is_active:
            smarter_token_authentication_failure.send(
                sender=self.__class__,
                user=user,
                token=masked_token,
            )
            logger.warning(
                "%s.authenticate_credentials() - token is not active for user %s, token: %s",
                self.formatted_class_name,
                user,
                masked_token,
            )
            raise AuthenticationFailed("Api key is not activated.")

        # update the last used time for the token
        smarter_auth_token.last_used_at = timezone.now()
        smarter_auth_token.save()

        # if the token is active, we can return the user and token as a tuple
        # exactly as the default token authentication does.
        smarter_token_authentication_success.send(
            sender=self.__class__,
            user=user,
            token=masked_token,
        )
        logger.info(
            "%s.authenticate_credentials() - successfully authenticated user %s", self.formatted_class_name, user
        )
        return (user, smarter_auth_token)
