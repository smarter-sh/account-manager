"""Test the WaffleSwitchedLoggerWrapper class."""

import logging

from django.test import SimpleTestCase

from am.lib.logging import WaffleSwitchedLoggerWrapper


class TestWaffleSwitchedLoggerWrapper(SimpleTestCase):
    """Test the WaffleSwitchedLoggerWrapper class."""

    def setUp(self):
        self.base_logger = logging.getLogger("am.lib.tests.test_logging")
        self.base_logger.setLevel(logging.DEBUG)
        self.addCleanup(self.base_logger.setLevel, logging.NOTSET)

    def test_condition_off_suppresses_debug_and_info_only(self):
        logger = WaffleSwitchedLoggerWrapper(self.base_logger, lambda level: False)
        with self.assertLogs(self.base_logger, level=logging.DEBUG) as logs:
            logger.debug("debug")
            logger.info("info")
            logger.warning("warning")
            logger.error("error")
            logger.critical("critical")
        self.assertEqual([r.getMessage() for r in logs.records], ["warning", "error", "critical"])

    def test_condition_on_logs_everything(self):
        logger = WaffleSwitchedLoggerWrapper(self.base_logger, lambda level: True)
        with self.assertLogs(self.base_logger, level=logging.DEBUG) as logs:
            logger.debug("debug %s", 1)
            logger.info("info")
        self.assertEqual([r.getMessage() for r in logs.records], ["debug 1", "info"])

    def test_no_condition_logs_everything(self):
        logger = WaffleSwitchedLoggerWrapper(self.base_logger)
        with self.assertLogs(self.base_logger, level=logging.DEBUG) as logs:
            logger.info("info")
        self.assertEqual(len(logs.records), 1)

    def test_disabled_level_is_not_logged(self):
        self.base_logger.setLevel(logging.WARNING)
        logger = WaffleSwitchedLoggerWrapper(self.base_logger, lambda level: True)
        with self.assertLogs(self.base_logger, level=logging.WARNING) as logs:
            logger.info("info")
            logger.warning("warning")
        self.assertEqual([r.getMessage() for r in logs.records], ["warning"])

    def test_set_condition(self):
        logger = WaffleSwitchedLoggerWrapper(self.base_logger, lambda level: False)
        logger.set_condition(lambda level: True)
        with self.assertLogs(self.base_logger, level=logging.DEBUG) as logs:
            logger.info("info")
        self.assertEqual(len(logs.records), 1)
