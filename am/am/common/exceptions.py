"""Module exceptions.py."""

import logging
import re

logger = logging.getLogger(__name__)


class AMException(Exception):
    """Exception raised for errors in the configuration."""

    def __init__(self, message: str = ""):
        self.message = message
        msg = self.get_formatted_err_message + ": " + self.message
        logger.error(msg)
        super().__init__(self.message)

    def __str__(self):
        return self.get_formatted_err_message + ": " + self.message

    @property
    def get_formatted_err_message(self):
        words = re.findall(r"(?:[A-Z]{2,}(?=[A-Z][a-z]|[0-9]|$))|(?:[A-Z][a-z]+)", type(self).__name__)
        return " ".join(word for word in words)


class AMConfigurationError(AMException):
    """Exception raised for errors in the configuration."""


class AMValueError(AMException):
    """Exception raised for illegal or invalid values."""


class AMBusinessRuleViolation(AMException):
    """Exception raised when policies are violated."""
