"""
Account Utilities.

This module provides foundational utilities for accessing, managing, and caching account and user data in the Account Manager platform.
It is the base model for all Django ORM operations in the project, and is designed for both performance and reliability.

Caching Overview
----------------

Two caching strategies are used:

- **LRU In-Memory Caching**:
  Fast, per-process caching for frequently accessed objects such as `User`, `Account`, and `UserProfile`.
  *Scope*: Only available within the current process; short-lived.

- **Redis-Based ORM Caching**:
  Persistent, cross-process caching for Django ORM objects.
  *Scope*: Shared across all processes; cache lifetime is controlled by expiration settings.
"""

import logging
import re
from typing import Any, Optional, Union

from django.contrib.auth.models import AnonymousUser

from am.apps.account.models import User, get_resolved_user
from am.common.conf import am_settings
from am.common.const import ACCOUNT_ACCOUNT_NUMBER
from am.common.exceptions import AMConfigurationError, AMValueError
from am.common.helpers.console_helpers import formatted_text
from am.lib.cache import cache_results
from am.lib.django import waffle
from am.lib.django.validators import AMValidator
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .models import (
    Account,
    UserProfile,
)


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return (
        waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING)
        or waffle.switch_is_active(AMWaffleSwitches.CACHE_LOGGING)
    ) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)
UserType = Union[AnonymousUser, User, None]


def get_cached_account(
    account_id: Optional[int] = None, account_number: Optional[str] = None, invalidate: bool = False
) -> Optional[Account]:
    """
    Retrieve an Account instance by its ID or account number, using in-memory and Redis-based caching.

    :param account_id: Integer, optional. The primary key of the account to retrieve.
    :param account_number: String, optional. The unique account number to retrieve.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.

    :returns: Account instance if found, otherwise None.

    .. note::

       If both ``account_id`` and ``account_number`` are provided, ``account_id`` takes precedence.

    .. attention::

       If the account does not exist, None is returned and a warning is logged.

    **Example usage**::

        # Retrieve by account ID
        account = get_cached_account(account_id=42)

        # Retrieve by account number
        account = get_cached_account(account_number="3141-5926-5359")

        # Invalidate cache before fetching
        account = get_cached_account(account_id=42, invalidate=True)
    """

    @cache_results()
    def cached_account_by_id(account_id) -> Optional[Account]:
        """Cache for account objects by ID."""
        logger.info("cached_account_by_id() retrieving and caching account %s", account_id)
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            logger.warning("cached_account_by_id() account with ID %s does not exist", account_id)
            return None
        return account

    @cache_results()
    def cached_account_by_number(account_number) -> Optional[Account]:
        """Cache for account objects by account number."""
        logger.info("cached_account_by_number() retrieving and caching account %s", account_number)
        try:
            account = Account.objects.get(account_number=account_number)
        except Account.DoesNotExist:
            logger.warning("cached_account_by_number() account with number %s does not exist", account_number)
            return None
        return account

    if account_id:
        return cached_account_by_id(account_id) if not invalidate else cached_account_by_id.invalidate(account_id)

    if account_number:
        return (
            cached_account_by_number(account_number)
            if not invalidate
            else cached_account_by_number.invalidate(account_number)
        )


def get_cached_default_account(invalidate: bool = False) -> Optional[Account]:
    """
    Retrieve the default account instance, using caching for performance.

    :param invalidate: Boolean, optional. If True, invalidates the cached result instead of fetching it.
    :returns: The default Account instance, or None if ``invalidate`` is True.

    .. important::

           The default account is determined by the ``is_default_account=True`` flag in the database.

    .. warning::

           If no default account exists, an exception may be raised.

    **Example usage**::

        # Get the default account
        default_account = get_cached_default_account()

        # Invalidate cache before fetching
        default_account = get_cached_default_account(invalidate=True)
    """

    @cache_results()
    def _get_default_account():
        account = Account.objects.get(is_default_account=True)
        logger.info("get_cached_default_account() retrieving and caching default account %s", account)
        return account

    return _get_default_account() if not invalidate else _get_default_account.invalidate()


def _get_account_for_user(user, invalidate: bool = False) -> Optional[Account]:
    if not user:
        return None

    user_id = getattr(user, "id", None)
    if not user_id:
        logger.warning("get_cached_account_for_user() user has no ID: %s", user)
        return None

    @cache_results()
    def _get_account_for_user_by_id(user_id):
        """Cache for user accounts."""
        user_profiles = UserProfile.objects.filter(user_id=user_id)
        for user_profile in user_profiles:
            if user_profile.account.is_default_account:
                logger.info(
                    "get_cached_account_for_user() retrieving and caching default account %s for user %s",
                    user_profile.account,
                    user,
                )
                return user_profile.account
        # If no default account is found, return the first account
        user_profile = user_profiles.first()
        if not user_profile:
            logger.warning("get_cached_account_for_user_by_id() no UserProfile found for user ID %s", user_id)
            return None
        account = user_profile.account
        logger.info(
            "_get_account_for_user_by_id() retrieving and caching default account %s for user ID %s",
            account,
            user_id,
        )
        return account

    return _get_account_for_user_by_id(user_id) if not invalidate else _get_account_for_user_by_id.invalidate(user_id)


def get_cached_account_for_user(user: Any, invalidate: bool = False) -> Optional[Account]:
    """
    Locate the account associated with a given user, using caching for performance.

    :param user: User instance (or compatible object). The user whose account should be located.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.
    :returns: Account instance if found, otherwise None.

    .. note::

           If the user is an AnonymousUser, None is returned.

    .. warning::

           If no account exists for the user, None is returned and a warning is logged.

    .. tip::

           Use ``invalidate=True`` after updating user-account relationships to ensure cache consistency.

    **Example usage**::

        # Locate account for a user
        account = get_cached_account_for_user(user)

        # Invalidate cache before fetching
        account = get_cached_account_for_user(user, invalidate=True)
    """
    if isinstance(user, AnonymousUser):
        return None
    return _get_account_for_user(user, invalidate=invalidate)


def _get_cached_user_profile(
    resolved_user: User, account: Optional[Account], invalidate: bool = False
) -> Optional[UserProfile]:

    @cache_results()
    def cached_user_profile(user_id, account_id):
        user_profile = UserProfile.objects.get(user_id=user_id, account_id=account_id)
        logger.info("cached_user_profile() retrieving and caching UserProfile %s", user_profile)
        return user_profile

    if resolved_user is None or account is None:
        logger.warning("get_cached_user_profile() cannot initialize with user: %s account: %s", resolved_user, account)
        return None

    return (
        cached_user_profile(resolved_user.id, account.id)
        if not invalidate
        else cached_user_profile.invalidate(resolved_user.id, account.id)
    )


def get_cached_user_profile(
    user: User, account: Optional[Account] = None, invalidate: bool = False
) -> Optional[UserProfile]:
    """
    Locate the UserProfile for a given user and account, using caching for performance.

    :param user: User instance. The user whose profile should be located.
    :param account: Account instance, optional. If not provided, the user's account is determined automatically.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.
    :returns: UserProfile instance if found, otherwise None.

    .. note::

           If ``account`` is not provided, it is resolved using the user's associated account.

    .. warning::

           If no account or user profile is found, None is returned and a warning is logged.

    .. tip::

           Use ``invalidate=True`` after updating user or account data to ensure cache consistency.

    **Example usage**::

        # Locate user profile for a user
        profile = get_cached_user_profile(user)

        # Locate user profile for a user and specific account
        profile = get_cached_user_profile(user, account=account)

        # Invalidate cache before fetching
        profile = get_cached_user_profile(user, account=account, invalidate=True)
    """
    account = account or get_cached_account_for_user(user, invalidate=invalidate)
    if not account:
        logger.warning("get_cached_user_profile() no account found for user: %s", user)
        return None

    # pylint: disable=W0212
    resolved_user = get_resolved_user(user)
    if isinstance(resolved_user, User):
        return _get_cached_user_profile(resolved_user, account, invalidate=invalidate)
    logger.warning("get_cached_user_profile() user is not resolvable: %s", user)
    return None


def get_cached_user_for_user_id(user_id: int, invalidate: bool = False) -> Optional[User]:
    """
    Retrieve a User instance by its primary key, using caching for performance.

    :param user_id: Integer. The primary key of the user to retrieve.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.
    :returns: User instance if found, otherwise None.

    .. warning::

           If no user exists for the given ID, None is returned and an error is logged.

    .. tip::

           Use ``invalidate=True`` after updating user data to ensure cache consistency.

    **Example usage**::

        # Retrieve user by ID
        user = get_cached_user_for_user_id(123)

        # Invalidate cache before fetching
        user = get_cached_user_for_user_id(123, invalidate=True)
    """

    @cache_results()
    def cached_user(user_id) -> Optional[User]:
        """Cache for user objects."""
        try:
            user = User.objects.get(id=user_id)
            logger.info("cached_user() retrieving and caching user %s", user)
            return user  # type: ignore[return-value]
        except User.DoesNotExist:
            logger.error("get_cached_user_for_user_id() user with ID %s does not exist", user_id)

    user = cached_user(user_id) if not invalidate else cached_user.invalidate(user_id)
    if user:
        logger.info("get_cached_user_for_user_id() retrieving and caching user %s", user)
    return user


def get_cached_admin_user_for_account(account: Account, invalidate: bool = False) -> User:
    """
    Retrieve the admin user for a given account, creating one if necessary.

    :param account: Account instance. The account for which to retrieve the admin user.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.
    :returns: User instance representing the account admin.

    .. important::

           If no admin user exists for the account, a new staff user and UserProfile will be created automatically.

    .. warning::

           If the account is missing or misconfigured, an exception is raised.

    .. tip::

           Use ``invalidate=True`` after updating admin user data to ensure cache consistency.

    **Example usage**::

        # Retrieve the admin user for an account
        admin_user = get_cached_admin_user_for_account(account)

        # Invalidate cache before fetching
        admin_user = get_cached_admin_user_for_account(account, invalidate=True)
    """
    if not account:
        raise AMValueError("Account is required")

    @cache_results()
    def admin_for_account(account_number: str) -> User:
        account = get_cached_account(account_number=account_number)
        if not account:
            raise AMConfigurationError(
                f"Failed to retrieve account with number {account_number}. Please ensure the account exists and is configured correctly."
            )
        console_prefix = formatted_text("get_cached_admin_user_for_account()")
        user_profile = UserProfile.objects.filter(account=account, user__is_staff=True).order_by("pk").first()
        if user_profile:
            logger.info(
                "%s found and cached admin UserProfile %s for account %s", console_prefix, user_profile, account
            )
            return user_profile.user
        else:
            # Create a new admin user and UserProfile. An account whose every profile is a test
            # profile is a test account, so its admin is a test profile too, and so is the admin's
            # account contact, whose emails are then sent quietly.
            profiles = UserProfile.objects.filter(account=account)
            is_test_account = profiles.exists() and not profiles.filter(is_test=False).exists()
            admin_email = f"{account_number}@{am_settings.root_domain}"
            admin_user = User.objects.create_user(username=account_number, email=admin_email, is_staff=True)
            logger.info("%s created new admin User %s for account %s", console_prefix, admin_user, account)
            user_profile = UserProfile.objects.create(user=admin_user, account=account, is_test=is_test_account)
            logger.info("%s created new admin UserProfile for user %s", console_prefix, user_profile)
        return user_profile.user

    account_number = account.account_number if isinstance(account, Account) else None
    if not account_number:
        raise AMValueError("Account number is required to retrieve admin user")
    return admin_for_account(account_number) if not invalidate else admin_for_account.invalidate(account_number)  # type: ignore[return-value]


def get_cached_smarter_admin_user_profile(invalidate: bool = False) -> Optional[UserProfile]:
    """
    Retrieve the admin UserProfile for the smarter account, using caching for performance.

    :param invalidate: Boolean, optional. If True, invalidates the cached result instead of fetching it.
    :returns: UserProfile instance for the smarter admin user, or None if ``invalidate`` is True.

    .. note::

           The smarter admin user is typically a superuser or staff user associated with the platform's main account.

    .. warning::

           If no suitable admin user exists, or the smarter account is misconfigured, an exception is raised.

    .. tip::

           Use ``invalidate=True`` after updating admin user or account data to ensure cache consistency.

    **Example usage**::

        # Retrieve the smarter admin user profile
        admin_profile = get_cached_smarter_admin_user_profile()

        # Invalidate cache before fetching
        admin_profile = get_cached_smarter_admin_user_profile(invalidate=True)
    """

    smarter_account = get_cached_account(account_number=ACCOUNT_ACCOUNT_NUMBER)
    if not smarter_account:
        raise AMConfigurationError(
            "Failed to retrieve smarter account. Please ensure the account exists and is configured correctly."
        )

    @cache_results()
    def cached_smarter_admin_user_profile(smarter_account_id):
        super_user_profile = (
            UserProfile.objects.filter(account_id=smarter_account_id, user__is_superuser=True).order_by("pk").first()
        )
        if super_user_profile:
            logger.info(
                "cached_smarter_admin_user_profile() retrieving and caching superuser UserProfile %s",
                super_user_profile,
            )
            return super_user_profile

        staff_user_profile = (
            UserProfile.objects.filter(account_id=smarter_account_id, user__is_staff=True).order_by("pk").first()
        )
        if staff_user_profile:
            logger.info(
                "cached_smarter_admin_user_profile() retrieving and caching staff UserProfile %s",
                staff_user_profile,
            )
            return staff_user_profile

        raise AMConfigurationError(
            "Failed to retrieve smarter admin user profile. Please ensure the account has a superuser or staff user."
        )

    return (
        cached_smarter_admin_user_profile(smarter_account.id)
        if not invalidate
        else cached_smarter_admin_user_profile.invalidate(smarter_account.id)
    )


def account_number_from_url(url: str, invalidate: bool = False) -> Optional[str]:
    """
    Extract the account number from a Account Manager URL, using caching for performance.

    :param url: String. The URL to parse for an account number.
    :param invalidate: Boolean, optional. If True, invalidates the cache before fetching.
    :returns: The extracted account number as a string, or None if not found.

    .. note::

           The function validates the URL format before extraction.

    .. warning::

           If the URL does not contain a valid account number, None is returned.

    .. tip::

           Use ``invalidate=True`` after updating URLs or account number patterns to ensure cache consistency.

    **Example usage**::

        # Extract account number from a URL
        account_number = account_number_from_url("https://hr.3141-5926-5359.alpha.api.example.com/")

        # Result: '3141-5926-5359'

        # Invalidate cache before fetching
        account_number = account_number_from_url("https://hr.3141-5926-5359.alpha.api.example.com/", invalidate=True)
    """
    if not url:
        return None

    @cache_results()
    def _account_number_from_url(url: str) -> Optional[str]:
        AMValidator.validate_url(url)
        match = re.search(AMValidator.ACCOUNT_ACCOUNT_NUMBER_REGEX, url)
        retval = match.group(0) if match else None
        if retval is not None:
            logger.info("account_number_from_url() extracted and cached account number %s from URL %s", retval, url)
        return retval

    return _account_number_from_url(url) if not invalidate else _account_number_from_url.invalidate(url)


def cache_invalidate(user: Optional[User] = None, account: Optional[Account] = None):
    """
    Invalidate all cache entries for the specified user and/or account.

    :param user: User instance, optional. The user whose cache entries should be invalidated.
    :param account: Account instance, optional. The account whose cache entries should be invalidated.

    .. important::

           At least one of ``user`` or ``account`` must be provided. If neither is given, an exception is raised.

    .. warning::

           If the user or account cannot be resolved, cache invalidation will not occur and a warning is logged.

    .. tip::

           Use this function after updating user or account data to ensure cache consistency across the platform.

    **Example usage**::

        # Invalidate cache for a user
        cache_invalidate(user=user)

        # Invalidate cache for an account
        cache_invalidate(account=account)

        # Invalidate cache for both user and account
        cache_invalidate(user=user, account=account)
    """
    resolved_user = get_resolved_user(user) if user else None

    if isinstance(resolved_user, User):
        user_profile = UserProfile.objects.filter(user=resolved_user).first()
        if not user_profile:
            # this can happen during new platform bootstrap initialization, so just log a warning and return
            logger.warning("cache_invalidate() no UserProfile found for user: %s", resolved_user)
            return
        resolved_account = user_profile.account
    elif isinstance(account, Account):
        resolved_account = account
        resolved_user = get_cached_admin_user_for_account(account, invalidate=True)
    else:
        raise AMValueError("either user or account is required")

    logger.info("cache_invalidate() invalidating cache for user: %s account: %s", resolved_user, resolved_account)

    get_cached_account(account_id=resolved_account.id, invalidate=True)
    get_cached_admin_user_for_account(account=resolved_account, invalidate=True)

    if isinstance(resolved_user, User):
        get_cached_account_for_user(user=resolved_user, invalidate=True)
        get_cached_user_profile(user=resolved_user, account=resolved_account, invalidate=True)
        get_cached_user_for_user_id(user_id=resolved_user.id, invalidate=True)
