"""Unit test base classes for Account Manager."""

from ..models import PaymentMethod
from ..serializers import (
    AccountMiniSerializer,
    AccountSerializer,
    PaymentMethodSerializer,
    UserProfileSerializer,
)
from .factories import (
    payment_method_factory,
    payment_method_factory_teardown,
)
from .mixins import TestAccountMixin


class TestSerializers(TestAccountMixin):
    """Test serializers for the account app."""

    payment_method: PaymentMethod = None

    @classmethod
    def setUpClass(cls):
        """Set up test data for the test case."""
        super().setUpClass()
        cls.payment_method = payment_method_factory(cls.account)

    @classmethod
    def tearDownClass(cls):
        """Tear down test data after the test case."""
        try:
            payment_method_factory_teardown(payment_method=cls.payment_method)
            cls.payment_method = None
        # pylint: disable=W0718
        except Exception:
            pass
        finally:
            super().tearDownClass()

    def test_account_serializer(self):
        """Test the AccountSerializer."""
        serializer = AccountSerializer(self.account)
        data = serializer.data
        self.assertIsInstance(data, dict)

    def test_account_mini_serializer(self):
        """Test the AccountMiniSerializer."""
        serializer = AccountMiniSerializer(self.account)
        data = serializer.data
        self.assertIsInstance(data, dict)

    def test_user_profile_serializer(self):
        """Test the UserProfileSerializer."""
        serializer = UserProfileSerializer(self.user_profile)
        data = serializer.data
        self.assertIsInstance(data, dict)

    def test_payment_method_serializer(self):
        """Test the PaymentMethodSerializer."""
        serializer = PaymentMethodSerializer(self.payment_method)
        data = serializer.data
        self.assertIsInstance(data, dict)
