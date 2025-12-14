# pylint: disable=wrong-import-position
"""Test User."""

from account.common.helpers.mailchimp_helpers import MailchimpHelper
from account.lib.unittest.base_classes import AMTestBase


class TestMailChimp(AMTestBase):
    """Test Account model"""

    def test_mailchimp_is_available(self):
        """Test that Mailchimp service is reachable."""
        if not MailchimpHelper().ping():
            self.fail("Mailchimp API is not reachable")
