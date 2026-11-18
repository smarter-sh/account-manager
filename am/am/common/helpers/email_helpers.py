"""Helper class for sending email via AWS Simple Email Service using SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Union, cast

from django.conf import settings

from am.common.conf import am_settings
from am.common.exceptions import AMException
from am.lib.django.validators import AMValidator

from ..classes import Singleton

logger = logging.getLogger(__name__)


class EmailHelperException(AMException):
    """Base class for Email helper exceptions."""


class EmailHelper(metaclass=Singleton):
    """
    Helper class for sending emails via AWS Simple Email Service (SES) using SMTP.

    This class provides utility methods for validating email addresses and sending emails
    through an SMTP server, with configuration provided by Django settings and custom
    application settings.

    The class is implemented as a singleton to ensure a single instance is used throughout
    the application.
    """

    @staticmethod
    def validate_mail_list(emails: Union[str, List[str]], quiet: bool = False) -> Union[List[str], None]:
        """
        Convert the input into a list and filter out any invalid email addresses.

        This method accepts either a single email address as a string or a list of email addresses.
        It validates each email address using the `AMValidator.is_valid_email` method.
        Invalid email addresses are filtered out, and warnings are logged if any are found,
        unless `quiet` is set to True.

        Parameters
        ----------
        emails : Union[str, List[str]]
            A single email address as a string, or a list of email addresses to validate.
        quiet : bool, optional
            If True, suppresses warning logs for invalid email addresses (default is False).

        Returns
        -------
        Union[List[str], None]
            A list of valid email addresses, or None if no valid addresses are found.

        Logs
        ----
        - Logs a warning if the input is not a string or list.
        - Logs a warning if invalid email addresses are found (unless `quiet` is True).
        - Logs a warning if no valid email addresses are found (unless `quiet` is True).
        """
        if isinstance(emails, str):
            mailto_list = [emails]
        elif isinstance(emails, list):
            mailto_list = emails
        else:
            logger.warning("invalid email address list provided, of type %s", type(emails).__name__)
            return None

        valid_emails = [email for email in mailto_list if AMValidator.is_valid_email(email)]

        invalid_count = len(set(mailto_list) - set(valid_emails))
        if invalid_count and not quiet:
            logger.warning("%s invalid email address(es) were found in send list", invalid_count)

        if len(valid_emails) == 0:
            if not quiet:
                logger.warning("no valid email addresses found in send list")
            return None

        return valid_emails

    # pylint: disable=too-many-arguments
    @staticmethod
    def send_email(subject, body, to: Union[str, List[str]], html=False, from_email=None, quiet: bool = False):
        """
        Send an email using the configured SMTP server.

        This method constructs and sends an email message using the SMTP configuration
        specified in the application settings. It supports sending plain text or HTML emails,
        and can optionally suppress actual sending for testing or development purposes.

        Parameters
        ----------
        subject : str
            The subject line of the email.
        body : str
            The body content of the email. If `html` is True, this should be HTML-formatted.
        to : Union[str, List[str]]
            The recipient email address or a list of recipient email addresses.
        html : bool, optional
            If True, sends the email as HTML. Otherwise, sends as plain text (default is False).
        from_email : str, optional
            The sender's email address. If not provided, uses the configured default sender.
        quiet : bool, optional
            If True, does not actually send the email and suppresses warnings (default is False).

        Raises
        ------
        EmailHelperException
            If an error occurs during sending and developer mode is enabled.

        Logs
        ----
        - Logs a warning if SMTP is not configured.
        - Logs information about emails that would have been sent in quiet mode.
        - Logs errors if sending fails due to SMTP or unexpected exceptions.
        """
        if not am_settings.smtp_is_configured:
            if not quiet:
                logger.warning(
                    "EmailHelper.send_email() SMTP not configured, would have sent subject '%s'",
                    subject,
                )
            return

        mail_to = EmailHelper.validate_mail_list(emails=to, quiet=quiet)
        if not mail_to:
            return

        if quiet:
            logger.info(
                "EmailHelper.send_email() quiet mode. would have sent subject '%s' to %s recipient(s)",
                subject,
                len(mail_to),
            )
            return

        # smtp_is_configured, checked above, guarantees that these settings are set.
        smtp_host = cast(str, am_settings.smtp_host)
        smtp_port = cast(int, am_settings.smtp_port)
        smtp_username = cast(str, am_settings.smtp_username)
        smtp_password = cast(str, am_settings.smtp_password)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email or cast(str, am_settings.smtp_from_email)
        msg["To"] = ", ".join(mail_to)
        bcc = [settings.ACCOUNT_EMAIL_ADMIN] if getattr(settings, "ACCOUNT_EMAIL_ADMIN", None) else []
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        part2 = MIMEText(body, "html") if html else MIMEText(body)
        msg.attach(part2)

        smtp_class = smtplib.SMTP_SSL if am_settings.smtp_use_ssl else smtplib.SMTP
        try:
            with smtp_class(smtp_host, smtp_port) as server:
                if am_settings.smtp_use_tls and not am_settings.smtp_use_ssl:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                # send_message() removes the Bcc header from what it sends, so the
                # Bcc recipients are only in the envelope.
                server.send_message(msg, from_addr=msg["From"], to_addrs=mail_to + bcc)
                logger.info("smtp email sent to %s recipient(s): %s", len(mail_to), subject)
        except smtplib.SMTPException as e:
            logger.error("smtp error while attempting to send email '%s': %s", subject, e)
            if am_settings.developer_mode:
                raise EmailHelperException(f"Error sending email: {e}") from e
        # pylint: disable=broad-except
        except Exception as e:
            logger.error("unexpected error while attempting to send email '%s': %s", subject, e)
            if am_settings.developer_mode:
                raise EmailHelperException(f"Error sending email: {e}") from e


email_helper = EmailHelper()
