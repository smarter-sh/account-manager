#!/usr/bin/env python
# pylint: disable=C0415
"""Django's command-line utility for administrative tasks."""
import logging
import os
import sys

from am.common.conf import account_settings


logger = logging.getLogger(__name__)


def main():
    """Run administrative tasks."""
    if not account_settings.environment:
        raise RuntimeError("The 'account_settings.environment' variable is not set.")
    logger.info("Environment variable 'account_settings.environment': %s", account_settings.environment)

    os.environ["DJANGO_SETTINGS_MODULE"] = "am.settings." + account_settings.environment
    logger.info("Using Django settings module: %s", os.environ["DJANGO_SETTINGS_MODULE"])

    if os.getenv("DEBUG", "false").lower() == "true":
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode is enabled.")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
