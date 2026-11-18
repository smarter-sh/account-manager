"""DRF knox authtoken model and manager."""

import uuid
from logging import getLogger
from typing import ClassVar, Optional

from django.db import models
from django.utils import timezone
from knox import crypto
from knox.models import AuthToken, AuthTokenManager
from knox.settings import CONSTANTS

from am.apps.account.models import User
from am.common.exceptions import AMBusinessRuleViolation
from am.lib.django.model_helpers import TimestampedModel

logger = getLogger(__name__)


###############################################################################
# API Key Management
###############################################################################
class AMAuthTokenManager(AuthTokenManager):
    """API Key manager."""

    def create(
        self,
        user: User,
        expiry=None,
        prefix=None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        **kwargs,
    ) -> tuple["AMAuthToken", str]:
        prefix = prefix or ""
        token = prefix + crypto.create_token_string()
        token_key = token[: CONSTANTS.TOKEN_KEY_LENGTH]
        digest = crypto.hash_token(token)
        if expiry is not None:
            expiry = timezone.now() + expiry

        auth_token = self.model(
            token_key=token_key,
            digest=digest,
            user=user,
            expiry=expiry,
            name=name,
            description=description,
            is_active=is_active,
            **kwargs,
        )
        auth_token.save()
        # never log the token, nor its token_key prefix: they are credentials.
        logger.info("Created API Key %s for user %s with expiry %s", auth_token.key_id, user, expiry)
        return auth_token, token


class AMAuthToken(AuthToken, TimestampedModel):
    """
    Represents a Account Manager API Key used for authenticating and authorizing access to the Account Manager.

    This model extends Knox's `AuthToken` and includes additional metadata and management features
    for API keys, such as naming, description, activation status, and usage tracking.

    **Parameters:**
        key_id (UUIDField): Unique identifier for the API key.
        name (str): Human-readable name for the API key.
        description (str, optional): Optional description of the API key's purpose.
        last_used_at (datetime, optional): Timestamp of the last usage of the API key.
        is_active (bool): Indicates whether the API key is currently active.

    **Usage Example:**

        .. code-block:: python

            # Creating an API key for a staff user
            user = User.objects.get(username="admin")
            token, key = AMAuthToken.objects.create(
                user=user,
                name="Production Key",
                description="Key for production API access"
            )

            # Deactivating the key
            token.is_active = False
            token.save()

    .. note::

        - API keys can only be created for staff users. Attempting to create a key for a non-staff user
          will raise a `AMBusinessRuleViolation`.
        - The `identifier` property returns a masked version of the key digest for display purposes.

    .. warning::

        - Ensure that API keys are managed securely. Deactivated keys cannot be used for authentication.

    Related Models
    --------------

    - ``User``: The owner of the API key.
    - ``TimestampedModel``: Provides created/modified timestamps.
    """

    objects: ClassVar[AMAuthTokenManager] = AMAuthTokenManager()

    # pylint: disable=C0115
    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    key_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    @property
    def identifier(self):
        return "******" + str(self.digest)[-4:]

    def save(self, *args, **kwargs):
        if not self.user.is_staff:
            raise AMBusinessRuleViolation("API Keys can only be created for staff users.")
        if self.created is None:
            self.created = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.name) + " (" + str(self.user) + ") " + str(self.identifier)
