"""Test the api app's signal receivers in am.apps.api.receivers."""

import logging
from unittest.mock import MagicMock, patch

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from am.apps.api import receivers
from am.apps.api.signals import api_request_completed, api_request_initiated
from am.lib.unittest.base_classes import AMTestBase


class FailingContent:
    """A response whose content can't be read as json or decoded."""

    @property
    def content(self):
        raise RuntimeError("no content")


class TestApiReceivers(AMTestBase):
    """Test the receivers of api_request_initiated and api_request_completed."""

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get("/api/v1/example/")
        self.instance = MagicMock()
        patcher = patch.object(receivers, "logger")
        self.logger = patcher.start()
        self.addCleanup(patcher.stop)

    def logged_values(self):
        """The arguments of the last logger.info() call."""
        return self.logger.info.call_args.args

    def test_should_log(self):
        """Receiver logging follows the RECEIVER_LOGGING switch and the log level."""
        with patch.object(receivers.waffle, "switch_is_active", return_value=True):
            self.assertTrue(receivers.should_log(logging.CRITICAL))
        with patch.object(receivers.waffle, "switch_is_active", return_value=False):
            self.assertFalse(receivers.should_log(logging.CRITICAL))

    def test_request_initiated(self):
        """Api_request_initiated logs the request path."""
        api_request_initiated.send(sender=self.__class__, instance=self.instance, request=self.request)
        self.logger.info.assert_called_once()
        self.assertIn("/api/v1/example/", self.logged_values())

    def test_request_completed_json(self):
        """A json response is logged as formatted json."""
        response = JsonResponse({"status": "ok"})
        api_request_completed.send(
            sender=self.__class__, instance=self.instance, request=self.request, response=response
        )
        self.logger.warning.assert_not_called()
        self.assertIn('"status": "ok"', self.logged_values()[-1])

    def test_request_completed_json_list(self):
        """A json response that is not a dict is logged as is."""
        response = JsonResponse([1, 2], safe=False)
        api_request_completed.send(
            sender=self.__class__, instance=self.instance, request=self.request, response=response
        )
        self.assertEqual(self.logged_values()[-1], [1, 2])

    def test_request_completed_not_json(self):
        """A response that is not json is logged as text."""
        response = HttpResponse(b"plain \xff text")
        api_request_completed.send(
            sender=self.__class__, instance=self.instance, request=self.request, response=response
        )
        self.logger.warning.assert_called_once()
        self.assertEqual(self.logged_values()[-1], "plain � text")

    def test_request_completed_unreadable(self):
        """A response whose content can't be read is logged as None."""
        api_request_completed.send(
            sender=self.__class__, instance=self.instance, request=self.request, response=FailingContent()
        )
        self.assertIsNone(self.logged_values()[-1])
