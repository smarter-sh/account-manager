"""Test the Account Manager waffle wrapper."""

from unittest.mock import MagicMock, patch

from django.db.utils import OperationalError, ProgrammingError
from django.test import TestCase

from .. import waffle
from ..waffle import AMWaffleSwitches


class TestAMWaffleSwitches(TestCase):
    """Test the AMWaffleSwitches class."""

    def test_all(self):
        switches = AMWaffleSwitches().all
        self.assertIn(AMWaffleSwitches.API_LOGGING, switches)
        self.assertEqual(len(switches), len(set(switches)))
        self.assertTrue(all(isinstance(switch, str) for switch in switches))


class TestIsDatabaseReady(TestCase):
    """Test the is_database_ready function."""

    def setUp(self):
        self.addCleanup(setattr, waffle.db_state, "ready", waffle.db_state.ready)
        waffle.db_state.ready = False

    def test_ready(self):
        self.assertTrue(waffle.is_database_ready())
        self.assertTrue(waffle.db_state.ready)

    def test_already_ready_skips_the_check(self):
        waffle.db_state.ready = True
        with patch("am.lib.django.waffle.connections") as mock_connections:
            self.assertTrue(waffle.is_database_ready())
        mock_connections.__getitem__.assert_not_called()

    @patch("am.lib.django.waffle.connections")
    def test_missing_table(self, mock_connections):
        mock_connections.__getitem__.return_value.introspection.table_names.return_value = ["auth_user"]
        self.assertFalse(waffle.is_database_ready())
        self.assertFalse(waffle.db_state.ready)

    @patch("am.lib.django.waffle.connections")
    def test_database_errors(self, mock_connections):
        for error in (OperationalError, ProgrammingError):
            with self.subTest(error=error):
                mock_connections.__getitem__.return_value.ensure_connection.side_effect = error("down")
                self.assertFalse(waffle.is_database_ready())


class TestSwitchIsActive(TestCase):
    """Test the switch_is_active function."""

    @patch("am.lib.django.waffle.waffle_orig")
    def test_active_and_inactive_switch(self, mock_waffle_orig: MagicMock):
        """The switch's own state is returned.

        (waffle's cache is shared redis, so the switch is mocked.)
        """
        get_switch = mock_waffle_orig.get_waffle_switch_model.return_value.get
        get_switch.return_value.is_active.return_value = True
        self.assertTrue(waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING))
        get_switch.assert_called_with(AMWaffleSwitches.VIEW_LOGGING)
        get_switch.return_value.is_active.return_value = False
        self.assertFalse(waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING))

    @patch("am.lib.django.waffle.is_database_ready", return_value=False)
    def test_database_not_ready(self, _):
        self.assertFalse(waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING))

    def test_switch_name_must_be_a_string(self):
        self.assertFalse(waffle.switch_is_active(42))  # type: ignore[arg-type]

    def test_unknown_switch(self):
        self.assertFalse(waffle.switch_is_active("my_switch"))

    @patch("am.lib.django.waffle.waffle_orig")
    def test_database_error(self, mock_waffle_orig: MagicMock):
        mock_waffle_orig.get_waffle_switch_model.return_value.get.side_effect = OperationalError("db error")
        self.assertFalse(waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING))

    @patch("am.lib.django.waffle.waffle_orig")
    def test_unexpected_error(self, mock_waffle_orig: MagicMock):
        mock_waffle_orig.get_waffle_switch_model.return_value.get.side_effect = ValueError("boom")
        self.assertFalse(waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING))
