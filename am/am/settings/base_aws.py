# pylint: disable=E0402,unused-wildcard-import,wildcard-import
"""Django base settings for environments deployed to AWS."""

import os

from am.common.conf import am_settings

from .base import *

logger.info("Loading am.settings.base_aws")

ALLOWED_HOSTS = ["*"]

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("CACHES_LOCATION", "redis://:am@am-redis-master.smarter-am-dev.svc.cluster.local:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Celery Configuration
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", "redis://:am@am-redis-master.smarter-am-dev.svc.cluster.local:6379/1"
)
CELERY_REDBEAT_REDIS_URL = CELERY_BROKER_URL
CELERY_BEAT_SCHEDULER = "redbeat.RedBeatScheduler"

# Database: DATABASES is base.py's, from am_settings.mysql_* (AM_MYSQL_* environment variables).


STRIPE_LIVE_SECRET_KEY = am_settings.stripe_live_secret_key
STRIPE_TEST_SECRET_KEY = am_settings.stripe_test_secret_key
STRIPE_LIVE_MODE = False  # Change to True in production
DJSTRIPE_WEBHOOK_SECRET = (
    "whsec_xxx"  # Get it from the section in the Stripe dashboard where you added the webhook endpoint
)
DJSTRIPE_USE_NATIVE_JSONFIELD = True  # We recommend setting to True for new installations
DJSTRIPE_FOREIGN_KEY_TO_FIELD = "id"

# SMARTER settings
ACCOUNT_API_SCHEMA = "https"

# Common security settings
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_PROXY_SSL_HEADER = None

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://[\w-]+\.(\d+-\d+-\d+)\.api\.smarter\.sh$",
    r"^https?://[\w-]+\.am\.smarter\.sh$",
    r"^https?://[\w-]+\.api\.smarter\.sh$",
]
# settings that affect whether the browser saves cookies
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

SMTP_SENDER = am_settings.smtp_sender or am_settings.environment_domain
SMTP_FROM_EMAIL = am_settings.smtp_from_email or "no-reply@" + SMTP_SENDER
