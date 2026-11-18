"""Test the account views of the Account Manager API (``am.apps.account.api.v1.views.account``)."""

from http import HTTPStatus

from am.apps.account.models import Account

from .mixins import TestAccountMixin
from .test_api import AccountApiTestMixin


class TestApiV1ViewsAccount(AccountApiTestMixin, TestAccountMixin):
    """Test AccountView and AccountListView."""

    def throwaway_account(self) -> Account:
        """
        An Account that the test may change or delete, deleted afterwards.

        :returns: The Account.
        """
        account = Account.objects.create(company_name=f"TestThrowaway_{self.generate_hash_suffix()}")
        self.addCleanup(Account.objects.filter(pk=account.pk).delete)
        return account

    # ------------------------------------------------------------------
    # AccountListView
    # ------------------------------------------------------------------
    def test_list_superuser_sees_every_account(self):
        """A superuser's list holds Accounts other than their own."""
        response = self.client_for(self.admin_user).get(self.url("account_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        ids = {account["id"] for account in response.json()}
        self.assertTrue({self.account.pk, self.other_account.pk} <= ids)

    def test_list_staff_sees_only_own_account(self):
        """A staff user's list holds only their own Account."""
        response = self.client_for(self.staff_user).get(self.url("account_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual([account["id"] for account in response.json()], [self.account.pk])

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def test_get_superuser_any_account(self):
        """A superuser may read another Account."""
        response = self.client_for(self.admin_user).get(self.url("account_view", self.other_account.pk))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["accountNumber"], self.other_account.account_number)

    def test_get_superuser_missing_account(self):
        """A superuser gets 404 for an Account that does not exist."""
        response = self.client_for(self.admin_user).get(self.url("account_view", 999999999))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_staff_own_account(self):
        """A staff user may read their own Account."""
        response = self.client_for(self.staff_user).get(self.url("account_view", self.account.pk))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["companyName"], self.account.company_name)

    def test_get_staff_other_account_is_forbidden(self):
        """A staff user may not read another Account."""
        response = self.client_for(self.staff_user).get(self.url("account_view", self.other_account.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_staff_without_profile_is_forbidden(self):
        """A staff user without a UserProfile is refused."""
        response = self.client_without_profile().get(self.url("account_view", self.account.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------
    def test_post_superuser_creates_account(self):
        """A superuser creates an Account, and gets it back with status 201."""
        company_name = f"TestCreated_{self.generate_hash_suffix()}"
        response = self.client_for(self.admin_user).post(
            self.url("account_view", self.account.pk), {"company_name": company_name}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        account = Account.objects.get(company_name=company_name)
        self.addCleanup(account.delete)
        self.assertEqual(response.json()["id"], account.pk)
        self.assertEqual(response.json()["companyName"], company_name)

    def test_post_unknown_field_is_bad_request(self):
        """A field that the Account does not have is a 400."""
        response = self.client_for(self.admin_user).post(
            self.url("account_view", self.account.pk), {"no_such_field": "x"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("no_such_field", response.json()["exception"])

    def test_post_list_body_is_bad_request(self):
        """A body that is not a json dict is a 400."""
        response = self.client_for(self.admin_user).post(
            self.url("account_view", self.account.pk), ["company_name"], content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_post_staff_is_forbidden(self):
        """A staff user may not create an Account."""
        company_name = f"TestForbidden_{self.generate_hash_suffix()}"
        response = self.client_for(self.staff_user).post(
            self.url("account_view", self.account.pk), {"company_name": company_name}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertFalse(Account.objects.filter(company_name=company_name).exists())

    # ------------------------------------------------------------------
    # PATCH
    # ------------------------------------------------------------------
    def test_patch_superuser_updates_account(self):
        """A superuser updates an Account; unknown keys and the id are ignored."""
        account = self.throwaway_account()
        response = self.client_for(self.admin_user).patch(
            self.url("account_view", account.pk),
            {"city": "Springfield", "id": 1, "no_such_field": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["city"], "Springfield")
        account.refresh_from_db()
        self.assertEqual(account.city, "Springfield")

    def test_patch_staff_updates_own_account(self):
        """A staff user may update their own Account."""
        original = self.account.phone_number
        self.addCleanup(Account.objects.filter(pk=self.account.pk).update, phone_number=original)
        response = self.client_for(self.staff_user).patch(
            self.url("account_view", self.account.pk), {"phone_number": "555-0100"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(Account.objects.get(pk=self.account.pk).phone_number, "555-0100")

    def test_patch_staff_other_account_is_forbidden(self):
        """A staff user may not update another Account."""
        response = self.client_for(self.staff_user).patch(
            self.url("account_view", self.other_account.pk), {"city": "Nowhere"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertNotEqual(Account.objects.get(pk=self.other_account.pk).city, "Nowhere")

    def test_patch_invalid_value_is_bad_request(self):
        """A value that fails the model's validation is a 400, and is not saved."""
        account = self.throwaway_account()
        response = self.client_for(self.admin_user).patch(
            self.url("account_view", account.pk), {"postal_code": "x" * 50}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        account.refresh_from_db()
        self.assertIsNone(account.postal_code)

    def test_patch_list_body_is_bad_request(self):
        """A body that is not a json dict is a 400."""
        account = self.throwaway_account()
        response = self.client_for(self.admin_user).patch(
            self.url("account_view", account.pk), ["city"], content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------
    def test_delete_superuser_deletes_account(self):
        """A superuser deletes an Account, and keeps their own UserProfile."""
        account = self.throwaway_account()
        response = self.client_for(self.admin_user).delete(self.url("account_view", account.pk))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(Account.objects.filter(pk=account.pk).exists())
        self.assertTrue(type(self.user_profile).objects.filter(pk=self.user_profile.pk).exists())

    def test_delete_missing_account(self):
        """Deleting an Account that does not exist is a 404."""
        response = self.client_for(self.admin_user).delete(self.url("account_view", 999999999))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_staff_is_forbidden(self):
        """A staff user may not delete an Account, not even their own."""
        response = self.client_for(self.staff_user).delete(self.url("account_view", self.account.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertTrue(Account.objects.filter(pk=self.account.pk).exists())
