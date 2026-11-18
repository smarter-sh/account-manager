"""Test the drf app's signal receivers."""

from unittest.mock import patch

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.drf.models import AMAuthToken
from am.lib.drf.signals import (
    smarter_token_authentication_failure,
    smarter_token_authentication_request,
    smarter_token_authentication_success,
)


class TestReceivers(TestAccountMixin):
    """Test that the receivers log AMAuthToken and token authentication events."""

    @patch("am.lib.drf.receivers.logger")
    def test_auth_token_save_and_delete(self, mock_logger):
        record, _ = AMAuthToken.objects.create(user=self.admin_user, name=self.name)
        record.description = "updated"
        record.save()
        record.delete()
        messages = [c.args[0] for c in mock_logger.info.call_args_list]
        self.assertEqual(sum("post_save" in m for m in messages), 2)
        self.assertEqual(sum("post_delete" in m for m in messages), 1)

    @patch("am.lib.drf.receivers.logger")
    def test_token_authentication_signals(self, mock_logger):
        smarter_token_authentication_request.send(sender=self.__class__, token="****abcd")
        smarter_token_authentication_success.send(sender=self.__class__, user=self.admin_user, token="****abcd")
        smarter_token_authentication_failure.send(sender=self.__class__, user=None, token="****abcd")
        self.assertEqual(mock_logger.info.call_count, 3)

    def test_should_log(self):
        from am.lib.drf.receivers import (
            should_log,  # pylint: disable=import-outside-toplevel
        )

        with patch("am.lib.drf.receivers.waffle.switch_is_active", return_value=False):
            self.assertFalse(should_log(50))
