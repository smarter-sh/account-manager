"""Test am.common.exceptions."""

from unittest.mock import patch

from am.common.exceptions import (
    AMBusinessRuleViolation,
    AMConfigurationError,
    AMException,
    AMValueError,
)
from am.lib.unittest.base_classes import AMTestBase


class TestExceptions(AMTestBase):
    """Test the Account Manager exceptions."""

    def test_message_is_prefixed_with_the_class_name(self):
        """Str() is the exception's class name, in words, then the message."""
        self.assertEqual(str(AMValueError("bad value")), "AM Value Error: bad value")
        self.assertEqual(str(AMConfigurationError("missing")), "AM Configuration Error: missing")
        self.assertEqual(str(AMBusinessRuleViolation("no")), "AM Business Rule Violation: no")

    def test_message_attribute_and_default(self):
        """The message is kept, and defaults to an empty string."""
        self.assertEqual(AMValueError("bad value").message, "bad value")
        self.assertEqual(AMException().message, "")

    def test_exceptions_are_logged(self):
        """Creating an exception logs it as an error."""
        with patch("am.common.exceptions.logger") as mock_logger:
            AMValueError("bad value")
        mock_logger.error.assert_called_once_with("AM Value Error: bad value")

    def test_hierarchy(self):
        """Every Account Manager exception is an AMException."""
        for exception_class in [AMValueError, AMConfigurationError, AMBusinessRuleViolation]:
            self.assertTrue(issubclass(exception_class, AMException))
        with self.assertRaises(AMException):
            raise AMValueError("bad value")
