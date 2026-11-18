"""Test the AMCommand base class."""

from io import StringIO

from django.core.management.base import OutputWrapper
from django.test import SimpleTestCase

from am.lib.django.management.base import AMCommand


class TestAMCommand(SimpleTestCase):
    """Test the AMCommand class."""

    def setUp(self):
        self.out = StringIO()
        self.command = AMCommand()
        self.command.stdout = OutputWrapper(self.out)

    def test_handle_begin(self):
        self.command.handle_begin()
        self.assertIn("manage.py", self.out.getvalue())
        self.assertIn("am.lib.django.management.base started.", self.out.getvalue())

    def test_handle_completed_success(self):
        self.command.handle_completed_success()
        self.assertIn("am.lib.django.management.base completed successfully.", self.out.getvalue())
        self.command.handle_completed_success("all done")
        self.assertIn("all done", self.out.getvalue())

    def test_handle_completed_failure_without_error(self):
        self.command.handle_completed_failure(msg="something to say")
        self.assertIn("something to say", self.out.getvalue())
        self.assertIn("am.lib.django.management.base failed.", self.out.getvalue())

    def test_handle_completed_failure_with_error_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            self.command.handle_completed_failure(err=ValueError("boom"))
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("failed with error: boom", self.out.getvalue())

    def test_parser_has_settings_output_option(self):
        parser = self.command.create_parser("manage.py", "am_command")
        self.assertTrue(parser.parse_args(["--settings_output"]).settings_output)
        self.assertFalse(parser.parse_args([]).settings_output)

    def test_handle_must_be_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.command.handle()
