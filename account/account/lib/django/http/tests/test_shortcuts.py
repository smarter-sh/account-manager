"""Test AMHttpResponse classes"""

from unittest.mock import MagicMock, patch

from account.lib.django.http.shortcuts import (
    AMHttpResponse,
    AMHttpResponseBadRequest,
    AMHttpResponseForbidden,
    AMHttpResponseNotFound,
    AMHttpResponseServerError,
)
from account.lib.unittest.base_classes import AMTestBase


class TestAMHttpResponses(AMTestBase):
    """Test AMHttpResponse classes."""

    def setUp(self):
        super().setUp()
        self.request = MagicMock()

    @patch("account.lib.django.http.shortcuts.render")
    def test_smarter_http_response_defaults(self, mock_render):
        mock_render.return_value.content = b"html"
        resp = AMHttpResponse(self.request)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"html", resp.content)
        self.assertEqual(resp.context["message"], "Something went wrong! Please try again later.")

    @patch("account.lib.django.http.shortcuts.render")
    def test_smarter_http_response_custom(self, mock_render):
        mock_render.return_value.content = b"custom"
        resp = AMHttpResponse(self.request, error_message="foo", status_code=201, template_file="foo.html")
        self.assertEqual(resp.status_code, 201)
        self.assertIn(b"custom", resp.content)
        self.assertEqual(resp.context["message"], "foo")

    @patch("account.lib.django.http.shortcuts.render")
    def test_bad_request(self, mock_render):
        mock_render.return_value.content = b"bad"
        resp = AMHttpResponseBadRequest(self.request)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"bad", resp.content)
        self.assertEqual(resp.context["message"], "Dohhhh, that's a bad request my friend.")

    @patch("account.lib.django.http.shortcuts.render")
    def test_forbidden(self, mock_render):
        mock_render.return_value.content = b"forbidden"
        resp = AMHttpResponseForbidden(self.request)
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"forbidden", resp.content)
        self.assertEqual(resp.context["message"], "Awe shucks, you're not allowed to do that.")

    @patch("account.lib.django.http.shortcuts.render")
    def test_not_found(self, mock_render):
        mock_render.return_value.content = b"notfound"
        resp = AMHttpResponseNotFound(self.request)
        self.assertEqual(resp.status_code, 404)
        self.assertIn(b"notfound", resp.content)
        self.assertEqual(resp.context["message"], "Oh no!!! We couldn't find that page.")

    @patch("account.lib.django.http.shortcuts.render")
    def test_server_error(self, mock_render):
        mock_render.return_value.content = b"servererror"
        resp = AMHttpResponseServerError(self.request)
        self.assertEqual(resp.status_code, 500)
        self.assertIn(b"servererror", resp.content)
        self.assertEqual(resp.context["message"], "Ugh!!! Something went wrong on our end.")
