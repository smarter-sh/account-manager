"""Test the user views of the Account Manager API (``am.apps.account.api.v1.views.user``)."""

from http import HTTPStatus

from am.apps.account.models import User, UserProfile

from .mixins import TestAccountMixin
from .test_api import AccountApiTestMixin


class TestApiV1ViewsUser(AccountApiTestMixin, TestAccountMixin):
    """Test UserView and UserListView."""

    def throwaway_user(self, account=None) -> User:
        """
        A user that the test may change or delete, with a UserProfile in ``account``; deleted afterwards.

        :param account: The Account, by default ``self.account``.
        :returns: The User.
        """
        user, _ = self.create_staff_user(account or self.account)
        user.is_staff = False
        user.save()
        self.addCleanup(User.objects.filter(pk=user.pk).delete)
        self.addCleanup(UserProfile.objects.filter(user_id=user.pk).delete)
        return user

    def new_user_data(self) -> dict:
        """
        The body of a request to create a user.

        :returns: The body.
        """
        slug = self.generate_hash_suffix()
        return {
            "username": f"test_new_user_{slug}",
            "password": "12345",
            "email": f"test-new-{slug}@example.com",
            "first_name": "Test",
            "last_name": "User",
            "is_superuser": True,
        }

    # ------------------------------------------------------------------
    # UserListView
    # ------------------------------------------------------------------
    def test_list_superuser_sees_every_user(self):
        """A superuser's list holds users of other Accounts."""
        response = self.client_for(self.admin_user).get(self.url("account_users_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        ids = {user["id"] for user in response.json()}
        self.assertTrue({self.admin_user.pk, self.other_user.pk} <= ids)

    def test_list_staff_sees_own_account_users(self):
        """A staff user's list holds the users of their Account, and no one else."""
        response = self.client_for(self.staff_user).get(self.url("account_users_list_view"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        ids = {user["id"] for user in response.json()}
        self.assertEqual(ids, {self.admin_user.pk, self.non_admin_user.pk, self.staff_user.pk})

    def test_post_creates_user_in_own_account(self):
        """POST creates a user in the request user's Account, ignoring fields such as is_superuser."""
        data = self.new_user_data()
        response = self.client_for(self.staff_user).post(
            self.url("account_users_list_view"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        user = User.objects.get(username=data["username"])
        self.addCleanup(user.delete)
        self.addCleanup(UserProfile.objects.filter(user=user).delete)
        self.assertEqual(response.json()["id"], user.pk)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(data["password"]))
        self.assertEqual(UserProfile.objects.get(user=user).account, self.account)
        self.assertFalse(UserProfile.objects.filter(user=self.staff_user).exclude(pk=self.staff_user_profile.pk))

    def test_post_missing_password_is_bad_request(self):
        """A body without a password is a 400."""
        data = self.new_user_data()
        del data["password"]
        response = self.client_for(self.staff_user).post(
            self.url("account_users_list_view"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("password", response.json()["error"])
        self.assertFalse(User.objects.filter(username=data["username"]).exists())

    def test_post_list_body_is_bad_request(self):
        """A body that is not a json dict is a 400."""
        response = self.client_for(self.staff_user).post(
            self.url("account_users_list_view"), ["username"], content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_post_duplicate_username_is_bad_request(self):
        """A username that is taken is a 400."""
        data = self.new_user_data()
        data["username"] = self.non_admin_user.username
        response = self.client_for(self.staff_user).post(
            self.url("account_users_list_view"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(User.objects.filter(username=data["username"]).count(), 1)

    def test_post_without_profile_is_forbidden(self):
        """A request user without a UserProfile may not create users."""
        data = self.new_user_data()
        response = self.client_without_profile().post(
            self.url("account_users_list_view"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertFalse(User.objects.filter(username=data["username"]).exists())

    # ------------------------------------------------------------------
    # UserView GET
    # ------------------------------------------------------------------
    def test_get_superuser_any_user(self):
        """A superuser may read a user of another Account."""
        response = self.client_for(self.admin_user).get(self.url("account_user_view", self.other_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["username"], self.other_user.username)

    def test_get_superuser_missing_user(self):
        """A superuser gets a json 404 for a user who does not exist."""
        response = self.client_for(self.admin_user).get(self.url("account_user_view", 999999999))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(response.json(), {"error": "Not found"})

    def test_get_staff_own_account_user(self):
        """A staff user may read a user of their own Account."""
        response = self.client_for(self.staff_user).get(self.url("account_user_view", self.non_admin_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["email"], self.non_admin_user.email)

    def test_get_staff_other_account_user_is_not_found(self):
        """A staff user gets 404 for a user of another Account."""
        response = self.client_for(self.staff_user).get(self.url("account_user_view", self.other_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_staff_without_profile_is_forbidden(self):
        """A staff user without a UserProfile is refused."""
        response = self.client_without_profile().get(self.url("account_user_view", self.non_admin_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    # ------------------------------------------------------------------
    # UserView PATCH
    # ------------------------------------------------------------------
    def test_patch_updates_allowed_fields_only(self):
        """PATCH changes the allowed fields, and ignores is_superuser and the password."""
        user = self.throwaway_user()
        response = self.client_for(self.staff_user).patch(
            self.url("account_user_view", user.pk),
            {"first_name": "Updated", "is_superuser": True, "password": "changed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["firstName"], "Updated")
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("12345"))

    def test_patch_list_body_is_bad_request(self):
        """A body that is not a json dict is a 400."""
        user = self.throwaway_user()
        response = self.client_for(self.admin_user).patch(
            self.url("account_user_view", user.pk), ["first_name"], content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_patch_staff_other_account_user_is_not_found(self):
        """A staff user may not update a user of another Account."""
        response = self.client_for(self.staff_user).patch(
            self.url("account_user_view", self.other_user.pk), {"first_name": "Hacked"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertNotEqual(User.objects.get(pk=self.other_user.pk).first_name, "Hacked")

    # ------------------------------------------------------------------
    # UserView DELETE
    # ------------------------------------------------------------------
    def test_delete_user_and_profile(self):
        """DELETE removes the user and its UserProfile."""
        user = self.throwaway_user()
        response = self.client_for(self.staff_user).delete(self.url("account_user_view", user.pk))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=user.pk).exists())

    def test_delete_self_is_forbidden(self):
        """A user may not delete themself."""
        response = self.client_for(self.staff_user).delete(self.url("account_user_view", self.staff_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.staff_user.pk).exists())

    def test_delete_staff_other_account_user_is_not_found(self):
        """A staff user may not delete a user of another Account."""
        response = self.client_for(self.staff_user).delete(self.url("account_user_view", self.other_user.pk))
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertTrue(User.objects.filter(pk=self.other_user.pk).exists())

    def test_delete_superuser_other_account_user(self):
        """A superuser may delete a user of another Account."""
        user = self.throwaway_user(account=self.other_account)
        response = self.client_for(self.admin_user).delete(self.url("account_user_view", user.pk))
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
