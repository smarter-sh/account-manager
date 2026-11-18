"""Test the /api/v1/tests/ endpoints and the api url configuration."""

from django.urls import reverse
from rest_framework.test import APIClient

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.drf.models import AMAuthToken

from .views.test_views import FauxDictSerializer, faux_dict, faux_list


class TestApiV1TestViews(TestAccountMixin):
    """Test the faux json endpoints under /api/v1/tests/."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.token_record, cls.token_key = AMAuthToken.objects.create(  # type: ignore[call-arg]
            name=cls.admin_user.username,
            user=cls.admin_user,
            description=cls.admin_user.username,
        )

    @classmethod
    def tearDownClass(cls):
        try:
            cls.token_record.delete()
        except AMAuthToken.DoesNotExist:
            pass
        super().tearDownClass()

    def test_urls(self):
        """The test endpoints are under /api/v1/tests/."""
        self.assertEqual(reverse("api:v1:tests:test_json_dict_unauthenticated"), "/api/v1/tests/unauthenticated/dict/")
        self.assertEqual(reverse("api:v1:tests:test_json_list_authenticated"), "/api/v1/tests/authenticated/list/")

    def test_api_root_redirects_to_v1(self):
        """/api/ redirects permanently to /api/v1/."""
        response = APIClient().get("/api/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "v1/")

    def test_unauthenticated_views(self):
        """The unauthenticated endpoints answer anyone."""
        client = APIClient()
        response = client.get(reverse("api:v1:tests:test_json_dict_unauthenticated"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), faux_dict)
        response = client.get(reverse("api:v1:tests:test_json_list_unauthenticated"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), faux_list)

    def test_authenticated_list_view_refuses_anonymous_requests(self):
        """The authenticated list endpoint refuses requests without credentials."""
        response = APIClient().get(reverse("api:v1:tests:test_json_list_authenticated"))
        self.assertNotEqual(response.status_code, 200)

    def test_authenticated_list_view(self):
        """The authenticated list endpoint answers a request with an api key."""
        headers = {"Authorization": f"Token {self.token_key}"}
        response = APIClient().get(reverse("api:v1:tests:test_json_list_authenticated"), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), faux_list)

    def test_authenticated_dict_view(self):
        """The authenticated dict endpoint refuses anonymous requests and answers one with an api key."""
        client = APIClient()
        url = reverse("api:v1:tests:test_json_dict_authenticated")
        # the view's login_required decorator answers an anonymous request with a redirect to the login page.
        anonymous = client.get(url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("login", anonymous["Location"])
        response = client.get(url, headers={"Authorization": f"Token {self.token_key}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), faux_dict)

    def test_faux_dict_serializer(self):
        """The serializer validates, creates and updates faux items."""
        serializer = FauxDictSerializer(data=faux_list[0])
        self.assertTrue(serializer.is_valid(), serializer.errors)
        item = serializer.save()
        self.assertEqual(item["id"], 1)
        serializer = FauxDictSerializer(item, data={**faux_list[0], "status": "updated"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save()["status"], "updated")
