"""WSGI config for Account Manager."""

# wsgi.py
import logging
import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

from account.common.conf import account_settings


os.environ["DJANGO_SETTINGS_MODULE"] = "account.settings." + account_settings.environment

application = get_wsgi_application()
application = WhiteNoise(application, root=settings.STATIC_ROOT)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.debug("WSGI config for Account Manager.")
logger.debug("WSGI application: %s", application)
logger.debug("DJANGO_SETTINGS_MODULE: %s", os.getenv("DJANGO_SETTINGS_MODULE"))
logger.debug("static_root: %s", settings.STATIC_ROOT)

__all__ = ["application"]
