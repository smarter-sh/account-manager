"""Django custom project settings"""

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
    am_settings.environment_domain,
    am_settings.environment_api_domain,
    f"*.{am_settings.environment_api_domain}",
]
"""
Supplemental list of allowed host/domain names for Smarter ChatBots/Agents.
This is specicific to Smarter and not officially part of Django settings.
"""

ACCOUNT_INTERNAL_IP_PREFIXES = ["192.168."]
"""
Supplemental list of internal IP prefixes used in account.lib.django.middleware.security.SmarterSecurityMiddleware
and account.lib.django.middleware security features.

The default value is based on the default internal IP range used by Kubernetes clusters
by default unless otherwise configured.
"""


# SMARTER platform settings
# -----------------------------------------------------------------------------
ACCOUNT_ROOT_DOMAIN = am_settings.root_domain
"""
Account Manager root domain. This is not currently used.
"""

ACCOUNT_CACHE_EXPIRATION = 60 * 1  # 1 minute
"""
Default cache expiration time for Django views that use page caching.

See: django.views.decorators.cache.cache_control and django.views.decorators.cache.cache_page
"""

ACCOUNT_API_SCHEMA = "http"
"""
Account Manager API schema (http or https).
"""

ACCOUNT_API_NAME = "Account Manager API"
"""
Name of the Account Manager API. Not currently used.
"""

ACCOUNT_API_DESCRIPTION = "An enterprise class plugin-based AI chatbot platform"
"""
Description of the Account Manager API. Not currently used.
"""

# Marketing and branding settings
# -----------------------------------------------------------------------------
ACCOUNT_BRANDING_CORPORATE_NAME = "Lawrence P. McDaniel, The Smarter Project"
"""
Smarter Branding. Provided to the Smarter web console dashboard
context processor for use in the common footer of html templates.
"""
ACCOUNT_BRANDING_SUPPORT_PHONE_NUMBER = "+1 (617) 834-6172"
ACCOUNT_BRANDING_SUPPORT_EMAIL = "support@smarter.sh"
ACCOUNT_BRANDING_ADDRESS = "851 Burlway Road, Suite 101, Burlingame, CA 94010"
ACCOUNT_BRANDING_CONTACT_URL = "https://lawrencemcdaniel.com/contact/"
ACCOUNT_BRANDING_SUPPORT_HOURS = "MON-FRI 9:00 AM - 5:00 PM GMT-6 (CST)"
ACCOUNT_BRANDING_URL_FACEBOOK = "#"
ACCOUNT_BRANDING_URL_TWITTER = "#"
ACCOUNT_BRANDING_URL_LINKEDIN = "#"
ACCOUNT_EMAIL_ADMIN = "lpm0073@gmail.com"


ACCOUNT_SENSITIVE_FILES_AMNESTY_PATTERNS = [
    re.compile(r"^/dashboard/account/password-reset-link/[^/]+/[^/]+/$"),
    re.compile(r"^/api(/.*)?$"),
    re.compile(r"^/admin(/.*)?$"),
    re.compile(r"^/plugin(/.*)?$"),
    re.compile(r"^/docs/manifest(/.*)?$"),
    re.compile(r"^/docs/json-schema(/.*)?$"),
    re.compile(r".*stackademy.*"),
    re.compile(r"^/\.well-known/acme-challenge(/.*)?$"),
]
"""
Sensitive file amnesty patterns used by account.lib.django.middleware.sensitive_files.SensitiveFileAccessMiddleware.
Requests matching these patterns will be allowed even if they match sensitive file names.

Do not modify this setting unless you fully understand the implications of doing so.
"""

WAFFLE_CREATE_MISSING_SWITCHES = True
"""
If True, enables automatic creation of missing waffle switches in the database during deployment
jobs. This is intended to simplify management of waffle switches in Account Manager deployments.
"""
