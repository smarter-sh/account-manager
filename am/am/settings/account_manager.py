"""Django custom project settings."""

import re

from am.common.conf import am_settings, bool_environment_variable

ACCOUNT_SETTINGS_OUTPUT = bool_environment_variable("ACCOUNT_SETTINGS_OUTPUT", False)
"""
If True, enables verbose output of Smarter run-time settings during Django startup.

This will generate a multi-line header in new terminal windows launched from
Kubernetes pods running Smarter services.
"""

# Supplements to Django settings
# -----------------------------------------------------------------------------
ACCOUNT_ALLOWED_HOSTS = [
    host[:-5] if host.endswith(":8000") else host
    for host in [
        am_settings.environment_domain,
        am_settings.environment_api_domain,
        f"*.{am_settings.environment_api_domain}",
    ]
]
"""
Supplemental list of allowed host/domain names for Smarter ChatBots/Agents.

This is specicific to Smarter and not officially part of Django settings.
"""

ACCOUNT_INTERNAL_IP_PREFIXES = ["192.168."]
"""
Supplemental list of internal IP prefixes used in account.lib.django.middleware.security.SmarterSecurityMiddleware.

and account.lib.django.middleware security features.

The default value is based on the default internal IP range used by Kubernetes clusters
by default unless otherwise configured.
"""


# SMARTER platform settings
# -----------------------------------------------------------------------------
ACCOUNT_ROOT_DOMAIN = am_settings.root_domain
"""
Account Manager root domain.

This is not currently used.
"""

ACCOUNT_CACHE_EXPIRATION = 60 * 1  # 1 minute
"""
Default cache expiration time for Django views that use page caching.

See: django.views.decorators.cache.cache_control and django.views.decorators.cache.cache_page
"""

ACCOUNT_API_SCHEMA = "http"
"""Account Manager API schema (http or https)."""

ACCOUNT_API_NAME = "Account Manager API"
"""
Name of the Account Manager API.

Not currently used.
"""

ACCOUNT_API_DESCRIPTION = "An enterprise class plugin-based AI chatbot platform"
"""
Description of the Account Manager API.

Not currently used.
"""

# Email
# -----------------------------------------------------------------------------
ACCOUNT_EMAIL_ADMIN = "lpm0073@gmail.com"
"""The administrator, who receives a blind copy of every email that email_helper sends."""


ACCOUNT_SENSITIVE_FILES_AMNESTY_PATTERNS = [
    re.compile(r"^/api(/.*)?$"),
    re.compile(r"^/admin(/.*)?$"),
    re.compile(r"^/\.well-known/acme-challenge(/.*)?$"),
]
"""
Sensitive file amnesty patterns used by account.lib.django.middleware.sensitive_files.SensitiveFileAccessMiddleware.

Requests matching these patterns will be allowed even if they match sensitive file names.

Do not modify this setting unless you fully understand the implications of doing so.
"""

WAFFLE_CREATE_MISSING_SWITCHES = True
"""
If True, enables automatic creation of missing waffle switches in the database during deployment.

jobs. This is intended to simplify management of waffle switches in Account Manager deployments.
"""
