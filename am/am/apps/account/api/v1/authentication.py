"""
Authentication of the Smarter platforms that call the subscription status api.

A platform sends its key (see :class:`am.apps.account.models.PlatformClient`) in the
``Authorization`` header, with its own scheme, so that the knox token middleware
(``Authorization: Token <key>``) leaves it alone::

    Authorization: Platform <key>
"""

import logging
from typing import Optional

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from am.apps.account.models import PlatformClient

logger = logging.getLogger(__name__)

PLATFORM_AUTH_SCHEME = "Platform"
"""The ``Authorization`` header's scheme for a platform key."""


class PlatformClientUser:
    """
    The request's user when a platform's key authenticates it: a platform, not a person.

    It is authenticated, but it is no Django user: it has no staff or superuser rights, and
    no permission, so a view that checks any of them refuses it.

    :param client: The platform.
    """

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, client: PlatformClient):
        self.client = client

    def has_perm(self, perm, obj=None) -> bool:  # pylint: disable=unused-argument
        """A platform has no Django permissions."""
        return False

    def __str__(self):
        return f"platform {self.client.host_name}"


class PlatformClientAuthentication(BaseAuthentication):
    """
    Authenticate a Smarter platform by the key in its ``Authorization: Platform <key>`` header.

    A request without that header is not authenticated by this class (it returns None). A
    request with the header and an unknown, wrong or inactive key is refused with 401.
    ``request.auth`` is the :class:`PlatformClient`.
    """

    def authenticate(self, request) -> Optional[tuple[PlatformClientUser, PlatformClient]]:
        """
        Authenticate the request by its platform key.

        :param request: The DRF request.
        :returns: The platform as the user, and the client as the auth, or None without a platform key.
        :raises AuthenticationFailed: If the header is malformed, or the key doesn't authenticate.
        """
        parts = get_authorization_header(request).split()
        if not parts or parts[0].decode("latin-1").lower() != PLATFORM_AUTH_SCHEME.lower():
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid platform key header.")
        client = PlatformClient.authenticate(parts[1].decode("latin-1"))
        if client is None:
            logger.warning("PlatformClientAuthentication.authenticate() refused a platform key")
            raise AuthenticationFailed("Invalid platform key.")
        return PlatformClientUser(client), client

    def authenticate_header(self, request) -> str:
        """
        Return the ``WWW-Authenticate`` value of a 401 answer.

        :param request: The DRF request.
        :returns: The scheme.
        """
        return PLATFORM_AUTH_SCHEME
