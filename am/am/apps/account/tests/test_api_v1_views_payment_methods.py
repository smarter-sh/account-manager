"""Test the payment method views of the Account Manager API (``am.apps.account.api.v1.views.payment_methods``)."""

from http import HTTPStatus

from am.apps.account.models import PaymentMethod

from .factories import payment_method_factory
from .mixins import TestAccountMixin
from .test_api import AccountApiTestMixin


class TestApiV1ViewsPaymentMethods(AccountApiTestMixin, TestAccountMixin):
    """Test PaymentMethodView and PaymentMethodsListView."""

    def throwaway_payment_method(self, account=None) -> PaymentMethod:
        """
        A PaymentMethod that the test may delete; deleted afterwards.

        :param account: The Account, by default ``self.account``.
        :returns: The PaymentMethod.
        """
        payment_method = payment_method_factory(account or self.account)
        self.addCleanup(PaymentMethod.objects.filter(pk=payment_method.pk).delete)
        return payment_method

    def test_list_superuser_sees_every_payment_method(self):
        """A superuser's list holds the PaymentMethods of every Account."""
        response = self.client_for(self.admin_user).get(self.url("account_payment_methods_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        ids = {payment_method["id"] for payment_method in response.json()}
        self.assertTrue({self.payment_method.pk, self.other_payment_method.pk} <= ids)

    def test_list_staff_sees_own_account_payment_methods(self):
        """A staff user's list holds only their Account's PaymentMethods."""
        response = self.client_for(self.staff_user).get(self.url("account_payment_methods_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual([payment_method["id"] for payment_method in response.json()], [self.payment_method.pk])
        self.assertEqual(response.json()[0]["account"], self.account.pk)

    def test_get_superuser_any_payment_method(self):
        """A superuser may read another Account's PaymentMethod."""
        response = self.client_for(self.admin_user).get(
            self.url("account_payment_method_view", self.other_payment_method.pk)
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["stripeId"], self.other_payment_method.stripe_id)

    def test_get_staff_own_payment_method(self):
        """A staff user may read their Account's PaymentMethod."""
        response = self.client_for(self.staff_user).get(self.url("account_payment_method_view", self.payment_method.pk))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["name"], self.payment_method.name)

    def test_get_staff_other_payment_method_is_not_found(self):
        """A staff user gets 404 for another Account's PaymentMethod."""
        response = self.client_for(self.staff_user).get(
            self.url("account_payment_method_view", self.other_payment_method.pk)
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_missing_payment_method(self):
        """A PaymentMethod that does not exist is a 404."""
        response = self.client_for(self.admin_user).get(self.url("account_payment_method_view", 999999999))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_staff_without_profile_is_forbidden(self):
        """A staff user without a UserProfile is refused."""
        response = self.client_without_profile().get(self.url("account_payment_method_view", self.payment_method.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_delete_staff_own_payment_method(self):
        """A staff user deletes their Account's PaymentMethod, and only it."""
        payment_method = self.throwaway_payment_method()
        response = self.client_for(self.staff_user).delete(self.url("account_payment_method_view", payment_method.pk))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(PaymentMethod.objects.filter(pk=payment_method.pk).exists())
        self.assertTrue(type(self.account).objects.filter(pk=self.account.pk).exists())
        self.assertTrue(type(self.staff_user_profile).objects.filter(pk=self.staff_user_profile.pk).exists())

    def test_delete_staff_other_payment_method_is_not_found(self):
        """A staff user may not delete another Account's PaymentMethod."""
        payment_method = self.throwaway_payment_method(account=self.other_account)
        response = self.client_for(self.staff_user).delete(self.url("account_payment_method_view", payment_method.pk))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertTrue(PaymentMethod.objects.filter(pk=payment_method.pk).exists())

    def test_delete_superuser_other_payment_method(self):
        """A superuser may delete another Account's PaymentMethod."""
        payment_method = self.throwaway_payment_method(account=self.other_account)
        response = self.client_for(self.admin_user).delete(self.url("account_payment_method_view", payment_method.pk))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(PaymentMethod.objects.filter(pk=payment_method.pk).exists())
