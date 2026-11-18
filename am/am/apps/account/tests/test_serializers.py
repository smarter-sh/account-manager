"""Test the account app's serializers (``am.apps.account.serializers``)."""

from datetime import date, timedelta

from ..enum import AMHostingPlanTypeEnum
from ..models import PaymentMethod, Subscription
from ..serializers import (
    AccountMiniSerializer,
    AccountSerializer,
    PaymentMethodSerializer,
    UserMiniSerializer,
    UserProfileSerializer,
    UserSerializer,
)
from .factories import (
    payment_method_factory,
    payment_method_factory_teardown,
)
from .mixins import TestAccountMixin


class TestSerializers(TestAccountMixin):
    """Test serializers for the account app: camelCase keys, and the fields each one exposes."""

    payment_method: PaymentMethod
    subscription: Subscription

    @classmethod
    def setUpClass(cls):
        """Create a PaymentMethod and a Subscription."""
        super().setUpClass()
        cls.payment_method = payment_method_factory(cls.account)
        cls.subscription = Subscription.objects.create(
            account=cls.account,
            plan_type=AMHostingPlanTypeEnum.HOSTED_PLATFORM.value,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

    @classmethod
    def tearDownClass(cls):
        """Delete the PaymentMethod and the Subscription."""
        payment_method_factory_teardown(payment_method=cls.payment_method)
        cls.subscription.delete()
        super().tearDownClass()

    def test_account_serializer(self):
        """AccountSerializer has every field, in camelCase."""
        data = AccountSerializer(self.account).data
        self.assertEqual(data["id"], self.account.pk)
        self.assertEqual(data["accountNumber"], self.account.account_number)
        self.assertEqual(data["companyName"], self.account.company_name)
        self.assertIn("postalCode", data)
        self.assertNotIn("company_name", data)

    def test_account_mini_serializer(self):
        """AccountMiniSerializer has only the account number."""
        self.assertEqual(AccountMiniSerializer(self.account).data, {"accountNumber": self.account.account_number})

    def test_user_serializer(self):
        """UserSerializer has the listed fields, and not the password."""
        data = UserSerializer(self.admin_user).data
        self.assertEqual(set(data), {"id", "username", "firstName", "lastName", "email", "isStaff", "isSuperuser"})
        self.assertTrue(data["isSuperuser"])

    def test_user_mini_serializer(self):
        """UserMiniSerializer has the username and email only."""
        self.assertEqual(
            UserMiniSerializer(self.non_admin_user).data,
            {"username": self.non_admin_user.username, "email": self.non_admin_user.email},
        )

    def test_user_profile_serializer(self):
        """UserProfileSerializer nests the mini User and Account."""
        data = UserProfileSerializer(self.user_profile).data
        self.assertEqual(data["user"]["username"], self.admin_user.username)
        self.assertEqual(data["account"]["accountNumber"], self.account.account_number)

    def test_payment_method_serializer(self):
        """PaymentMethodSerializer has every field, in camelCase."""
        data = PaymentMethodSerializer(self.payment_method).data
        self.assertEqual(data["name"], self.payment_method.name)
        self.assertEqual(data["stripeId"], self.payment_method.stripe_id)
        self.assertEqual(data["account"], self.account.pk)
