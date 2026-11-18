"""Test am.common.helpers.email_helpers.

Every SMTP connection is mocked.
"""

import smtplib
from email import message_from_bytes
from unittest.mock import MagicMock, patch

from am.common.helpers.email_helpers import (
    EmailHelper,
    EmailHelperException,
    email_helper,
)
from am.lib.unittest.base_classes import AMTestBase

MODULE = "am.common.helpers.email_helpers"
# setUp() patches smtplib.SMTP itself, so keep the real class for the Bcc test
REAL_SMTP = smtplib.SMTP


def smtp_settings(**overrides) -> MagicMock:
    """A stand-in for am_settings with SMTP configured."""
    values = {
        "smtp_is_configured": True,
        "smtp_from_email": "no-reply@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "user",
        "smtp_password": "password",
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
        "developer_mode": False,
    }
    values.update(overrides)
    return MagicMock(**values)


class TestEmailHelper(AMTestBase):
    """Test EmailHelper."""

    def setUp(self):
        super().setUp()
        # no test may reach a real SMTP server
        self.smtp = self.enter_patch(f"{MODULE}.smtplib.SMTP")
        self.smtp_ssl = self.enter_patch(f"{MODULE}.smtplib.SMTP_SSL")
        self.server = self.smtp.return_value.__enter__.return_value
        self.ssl_server = self.smtp_ssl.return_value.__enter__.return_value
        self.django_settings = self.enter_patch(f"{MODULE}.settings")
        self.django_settings.ACCOUNT_EMAIL_ADMIN = "admin@example.com"
        self.am_settings = self.enter_patch(f"{MODULE}.am_settings", new=smtp_settings())

    def enter_patch(self, target, **kwargs):
        """Start a patch that is stopped after the test."""
        patcher = patch(target, **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def sent_message(self, server):
        """The (message, from_addr, to_addrs) of the one email sent through ``server``."""
        server.send_message.assert_called_once()
        call = server.send_message.call_args
        return call.args[0], call.kwargs["from_addr"], call.kwargs["to_addrs"]

    # -------------------------------------------------------------------------
    # validate_mail_list()
    # -------------------------------------------------------------------------
    def test_email_helper_is_a_singleton(self):
        """EmailHelper() always returns the module's email_helper."""
        self.assertIs(EmailHelper(), email_helper)

    def test_validate_mail_list_valid(self):
        """Valid addresses are returned, as a list."""
        emails = ["a@example.com", "b@example.com"]
        self.assertEqual(EmailHelper.validate_mail_list(emails), emails)
        self.assertEqual(EmailHelper.validate_mail_list("a@example.com"), ["a@example.com"])

    @patch(f"{MODULE}.logger")
    def test_validate_mail_list_invalid(self, mock_logger):
        """Invalid addresses are dropped, with a warning that doesn't name them."""
        self.assertEqual(EmailHelper.validate_mail_list(["a@example.com", "bad"]), ["a@example.com"])
        mock_logger.warning.assert_called_once()
        self.assertNotIn("bad", str(mock_logger.warning.call_args))

    @patch(f"{MODULE}.logger")
    def test_validate_mail_list_none_valid(self, mock_logger):
        """No valid address returns None, quiet or not."""
        self.assertIsNone(EmailHelper.validate_mail_list(["bad"]))
        self.assertEqual(mock_logger.warning.call_count, 2)

        mock_logger.reset_mock()
        self.assertIsNone(EmailHelper.validate_mail_list(["bad"], quiet=True))
        self.assertIsNone(EmailHelper.validate_mail_list([], quiet=True))
        mock_logger.warning.assert_not_called()

    @patch(f"{MODULE}.logger")
    def test_validate_mail_list_wrong_type(self, mock_logger):
        """Anything but a str or a list returns None."""
        self.assertIsNone(EmailHelper.validate_mail_list(42))  # type: ignore[arg-type]
        mock_logger.warning.assert_called_once()

    # -------------------------------------------------------------------------
    # send_email()
    # -------------------------------------------------------------------------
    def test_send_email(self):
        """A plain text email goes to the recipients and, in the envelope only, the admin."""
        EmailHelper.send_email("subject", "body", ["a@example.com", "b@example.com"])

        self.smtp.assert_called_once_with("smtp.example.com", 587)
        self.smtp_ssl.assert_not_called()
        self.server.starttls.assert_called_once()
        self.server.login.assert_called_once_with("user", "password")
        message, from_addr, to_addrs = self.sent_message(self.server)
        self.assertEqual(from_addr, "no-reply@example.com")
        self.assertEqual(to_addrs, ["a@example.com", "b@example.com", "admin@example.com"])
        self.assertEqual(message["To"], "a@example.com, b@example.com")
        self.assertEqual(message["Subject"], "subject")
        part = message.get_payload()[0]
        self.assertEqual(part.get_content_type(), "text/plain")
        self.assertEqual(part.get_payload(), "body")

    def test_send_email_bcc_is_not_in_the_message(self):
        """Send_message() strips the Bcc header from what it sends."""
        EmailHelper.send_email("subject", "body", "a@example.com")
        message, from_addr, to_addrs = self.sent_message(self.server)
        self.assertEqual(message["Bcc"], "admin@example.com")

        # run the standard library's send_message() on an unconnected client, to see what it sends
        real_server = REAL_SMTP.__new__(REAL_SMTP)
        real_server.ehlo_or_helo_if_needed = MagicMock()
        real_server.sendmail = MagicMock()
        REAL_SMTP.send_message(real_server, message, from_addr=from_addr, to_addrs=to_addrs)
        sent = message_from_bytes(real_server.sendmail.call_args.args[2])
        self.assertIsNone(sent["Bcc"])
        self.assertEqual(real_server.sendmail.call_args.args[1], ["a@example.com", "admin@example.com"])

    def test_send_email_html_and_from_email(self):
        """HTML bodies and a custom sender are used as given."""
        EmailHelper.send_email("subject", "<p>hi</p>", "a@example.com", html=True, from_email="me@example.com")
        message, from_addr, _ = self.sent_message(self.server)
        self.assertEqual(from_addr, "me@example.com")
        self.assertEqual(message.get_payload()[0].get_content_type(), "text/html")

    def test_send_email_without_admin_bcc(self):
        """Without ACCOUNT_EMAIL_ADMIN, only the recipients receive the email."""
        self.django_settings.ACCOUNT_EMAIL_ADMIN = ""
        EmailHelper.send_email("subject", "body", "a@example.com")
        message, _, to_addrs = self.sent_message(self.server)
        self.assertEqual(to_addrs, ["a@example.com"])
        self.assertIsNone(message["Bcc"])

    def test_send_email_ssl(self):
        """With smtp_use_ssl, the connection is SMTP_SSL, without STARTTLS."""
        self.am_settings.smtp_use_ssl = True
        EmailHelper.send_email("subject", "body", "a@example.com")
        self.smtp.assert_not_called()
        self.smtp_ssl.assert_called_once_with("smtp.example.com", 587)
        self.ssl_server.starttls.assert_not_called()
        self.sent_message(self.ssl_server)

    def test_send_email_without_tls(self):
        """Without smtp_use_tls, STARTTLS is not used."""
        self.am_settings.smtp_use_tls = False
        EmailHelper.send_email("subject", "body", "a@example.com")
        self.server.starttls.assert_not_called()
        self.sent_message(self.server)

    @patch(f"{MODULE}.logger")
    def test_send_email_smtp_not_configured(self, mock_logger):
        """Without SMTP configuration, nothing is sent."""
        self.am_settings.smtp_is_configured = False
        EmailHelper.send_email("subject", "body", "a@example.com")
        mock_logger.warning.assert_called_once()
        EmailHelper.send_email("subject", "body", "a@example.com", quiet=True)
        mock_logger.warning.assert_called_once()
        self.smtp.assert_not_called()

    def test_send_email_no_valid_recipient(self):
        """Without a valid recipient, nothing is sent."""
        EmailHelper.send_email("subject", "body", ["bad"])
        self.smtp.assert_not_called()

    @patch(f"{MODULE}.logger")
    def test_send_email_quiet(self, mock_logger):
        """Quiet mode logs what it would have sent, without the addresses, and sends nothing."""
        EmailHelper.send_email("subject", "body", "a@example.com", quiet=True)
        self.smtp.assert_not_called()
        mock_logger.info.assert_called_once()
        self.assertNotIn("a@example.com", str(mock_logger.info.call_args))

    @patch(f"{MODULE}.logger")
    def test_send_email_smtp_error(self, mock_logger):
        """SMTP errors are logged, and raised only in developer mode."""
        self.server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        EmailHelper.send_email("subject", "body", "a@example.com")
        mock_logger.error.assert_called_once()

        self.am_settings.developer_mode = True
        with self.assertRaises(EmailHelperException):
            EmailHelper.send_email("subject", "body", "a@example.com")

    @patch(f"{MODULE}.logger")
    def test_send_email_unexpected_error(self, mock_logger):
        """Other errors are logged, and raised only in developer mode."""
        self.server.send_message.side_effect = OSError("connection reset")
        EmailHelper.send_email("subject", "body", "a@example.com")
        mock_logger.error.assert_called_once()

        self.am_settings.developer_mode = True
        with self.assertRaises(EmailHelperException):
            EmailHelper.send_email("subject", "body", "a@example.com")
