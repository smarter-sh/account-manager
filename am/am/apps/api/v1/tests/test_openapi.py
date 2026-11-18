"""Test the OpenAPI schema view in am.apps.api.v1.views.openapi."""

from unittest.mock import patch

from django.test import Client, TestCase
from drf_yasg.generators import OpenAPISchemaGenerator

from am.apps.api.v1.views.openapi import ApiKeySchemaGenerator, api_info
from am.urls import api as api_urls


class TestOpenApi(TestCase):
    """Test the swagger page and the schema generator."""

    def test_security_definitions_add_api_key_auth(self):
        """The generator adds an api key definition to the default ones."""
        generator = ApiKeySchemaGenerator(info=api_info, patterns=api_urls.urlpatterns)
        definitions = generator.get_security_definitions()
        self.assertEqual(definitions["ApiKeyAuth"]["type"], "apiKey")
        self.assertEqual(definitions["ApiKeyAuth"]["name"], "Authorization")
        self.assertEqual(definitions["ApiKeyAuth"]["in"], "header")

    def test_security_definitions_without_defaults(self):
        """Without default definitions, the api key definition is the only one."""
        generator = ApiKeySchemaGenerator(info=api_info, patterns=api_urls.urlpatterns)
        with patch.object(OpenAPISchemaGenerator, "get_security_definitions", return_value=None):
            self.assertEqual(list(generator.get_security_definitions()), ["ApiKeyAuth"])

    def test_swagger_json(self):
        """The swagger page serves the schema, with the api key definition."""
        response = Client().get("/swagger/", {"format": "openapi"})
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["info"]["title"], api_info.title)
        self.assertIn("ApiKeyAuth", schema["securityDefinitions"])
