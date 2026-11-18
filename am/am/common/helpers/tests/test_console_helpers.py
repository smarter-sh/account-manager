"""Test am.common.helpers.console_helpers."""

from am.common.helpers.console_helpers import (
    formatted_json,
    formatted_text,
    formatted_text_green,
    formatted_text_red,
)
from am.lib.unittest.base_classes import AMTestBase


class TestConsoleHelpers(AMTestBase):
    """Test the ANSI color formatters."""

    def test_formatted_json(self):
        """Formatted_json() serializes to green json."""
        result = formatted_json({"a": 1})
        self.assertTrue(result.startswith("\033[32m"))
        self.assertTrue(result.endswith("\033[0m"))
        self.assertIn('"a": 1', result)
        result = formatted_json([1, 2])
        self.assertEqual(result.replace("\033[32m", "").replace("\033[0m", "").split(), ["[", "1,", "2", "]"])

    def test_formatted_text(self):
        """Each formatter wraps the text in its color and a reset."""
        self.assertEqual(formatted_text("hello"), "\033[1;31mhello\033[0m")
        self.assertEqual(formatted_text_green("hello"), "\033[92mhello\033[0m")
        self.assertEqual(formatted_text_red("hello"), "\033[91mhello\033[0m")
