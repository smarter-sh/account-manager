"""Test the view_helpers."""

from http import HTTPStatus
from typing import cast
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.test import RequestFactory, TestCase

from am.lib.django import view_helpers


class RobotsView(view_helpers.AMWebTxtView):
    """A text view of a template that exists."""

    template_path = "robots.txt"


class HtmlView(view_helpers.AMWebHtmlView):
    """An html view whose template the tests patch."""

    template_path = "page.html"
    context = {"title": "test"}


class NeverCachedView(view_helpers.AMNeverCachedWebView):
    """A never-cached html view whose template the tests patch."""

    template_path = "page.html"


def fake_render(html: str):
    """Return a stand-in for django.shortcuts.render that returns html."""

    def render(request, template_name, context):
        return HttpResponse(html)

    return render


class TestViewHelpers(TestCase):
    """Test the view_helpers module."""

    def setUp(self):
        self.factory = RequestFactory()

    def get(self, path="/"):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return request

    def test_redirect_and_expire_cache(self):
        response = view_helpers.redirect_and_expire_cache("/foo/")
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], "/foo/")
        self.assertEqual(response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["Expires"], "0")

    def test_remove_comments(self):
        view = view_helpers.AMView()
        self.assertEqual(view.remove_comments("<div><!-- a -->content<!-- b --></div>"), "<div>content</div>")

    def test_view_init_with_request(self):
        """The view initializes AMRequestMixin from a positional or keyword request."""
        request = self.get("/robots.txt")
        self.assertEqual(view_helpers.AMView(request).url, "http://testserver/robots.txt/")
        self.assertEqual(view_helpers.AMView(request=request).url, "http://testserver/robots.txt/")

    def test_text_view(self):
        response = cast(HttpResponse, RobotsView.as_view()(self.get("/robots.txt")))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertNotIn(b"<!--", response.content)

    @patch("am.lib.django.view_helpers.render", new=fake_render("<p><!-- developer note -->Hello</p>"))
    def test_html_view_strips_comments(self):
        response = cast(HttpResponse, HtmlView.as_view()(self.get()))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertEqual(response.content, b"<p>Hello</p>")

    @patch("am.lib.django.view_helpers.render", new=fake_render("<p>Hello</p>"))
    def test_never_cached_view(self):
        response = NeverCachedView.as_view()(self.get())
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("no-cache", response["Cache-Control"])

    def test_render_error_is_raised(self):
        """A template error is logged and raised, not turned into an empty page."""
        view = view_helpers.AMView()
        with patch("am.lib.django.view_helpers.logger") as mock_logger:
            with self.assertRaises(TemplateDoesNotExist):
                view.render_clean_html(self.get(), "does-not-exist.html")
        mock_logger.error.assert_called_once()
