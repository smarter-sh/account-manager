"""Dict factories for testing views."""

import logging
import random
import uuid
from datetime import datetime
from typing import Optional

from am.apps.account.models import (
    Account,
    PaymentMethod,
    User,
    UserProfile,
)
from am.apps.account.utils import get_cached_user_profile
from am.common.conf import am_settings
from am.common.utils import camel_to_snake, hash_factory
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper
from am.lib.unittest.base_classes import AMTestBase


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


def admin_user_factory(account: Optional[Account] = None) -> tuple[User, Account, UserProfile]:
    hashed_slug = hash_factory()
    username = camel_to_snake(f"testAdminUser_{hashed_slug}")
    email = f"test-admin-{hashed_slug}@mail.com"
    first_name = f"TestAdminFirstName_{hashed_slug}"
    last_name = f"TestAdminLastName_{hashed_slug}"
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        username=username,
        password="12345",
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    logger.info("admin_user_factory() Created admin user: %s", username)
    account = account or Account.objects.create(
        company_name=f"TestAccount_AdminUser_{hashed_slug}", phone_number="123-456-789"
    )
    logger.info("admin_user_factory() Created account: %s", account.id)  # type: ignore[return-value]
    user_profile = UserProfile.objects.create(user=user, account=account, is_test=True)
    logger.info("admin_user_factory() Created user profile %s", user_profile)

    return user, account, user_profile


def mortal_user_factory(account: Optional[Account] = None) -> tuple[User, Account, UserProfile]:
    hashed_slug = hash_factory()
    username = camel_to_snake(f"testAdminUser_{hashed_slug}")
    email = f"test-mortal-{hashed_slug}@mail.com"
    first_name = f"TestMortalFirstName_{hashed_slug}"
    last_name = f"TestMortalLastName_{hashed_slug}"
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        username=username,
        password="12345",
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    logger.info("mortal_user_factory() Created mortal user: %s", username)
    account = account or Account.objects.create(
        company_name=f"TestAccount_MortalUser_{hashed_slug}", phone_number="123-456-789"
    )
    logger.info("mortal_user_factory() Created/set account: %s", account.id)  # type: ignore[return-value]
    user_profile = UserProfile.objects.create(user=user, account=account, is_test=True)
    logger.info("mortal_user_factory() Created user profile %s", user_profile)

    return user, account, user_profile


def factory_account_teardown(user: User, account: Optional[Account], user_profile: UserProfile):
    if user and account and not user_profile:
        user_profile = get_cached_user_profile(user=user, account=account)
    elif user and not user_profile:
        user_profile = UserProfile.objects.filter(user=user).first()
    try:
        if user_profile:
            lbl = str(user_profile)
            user_profile.delete()
            logger.info("factory_account_teardown() Deleted user profile for %s", lbl)

    except UserProfile.DoesNotExist:
        pass
    try:
        if user:
            lbl = str(user)
            user.delete()
            logger.info("factory_account_teardown() Deleted user: %s", lbl)
    except User.DoesNotExist:
        pass
    try:
        if account:
            lbl = str(account)
            account.delete()
            logger.info("factory_account_teardown() Deleted account: %s", lbl)
    except Account.DoesNotExist:
        pass


def billing_address_factory():
    """Factory for testing billing addresses."""

    return {
        "id": str(uuid.uuid4()),
        "is_primary": True,
        "address1": "123 Main St",
        "address2": "Apt 123",
        "city": "Anytown",
        "state": "CA",
        "zip": "12345",
        "country": "US",
    }


def payment_method_factory(account: Account):
    """
    Factory for creating a PaymentMethod object for testing.
    """

    payment_method = PaymentMethod.objects.create(
        account=account,
        name=camel_to_snake("TestPaymentMethod" + AMTestBase.generate_hash_suffix()),
        stripe_id="test-stripe-id",
        card_type="test_card_type",
        card_last_4=random.randint(1000, 9999),
        card_exp_month=random.randint(1, 12),
        card_exp_year=random.randint(datetime.now().year, datetime.now().year + 7),
        is_default=True,
    )
    logger.info("payment_method_factory() Created payment method: %s", payment_method.name)
    return payment_method


def payment_method_factory_teardown(payment_method: PaymentMethod):
    try:
        if payment_method:
            lbl = str(payment_method)
            payment_method.delete()
            logger.info("payment_method_factory_teardown() Deleted payment method: %s", lbl)
    except PaymentMethod.DoesNotExist:
        pass
    except Exception as e:
        logger.error("payment_method_factory_teardown() Error deleting payment method: %s", e)
        raise
