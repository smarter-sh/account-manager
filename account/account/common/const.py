# pylint: disable=E1101
"""A module containing constants for the OpenAI API."""
import importlib.util
import logging
import os
from pathlib import Path
from typing import Dict

import hcl2


logger = logging.getLogger(__name__)

ACCOUNT_ACCOUNT_NUMBER = "3141-5926-5359"
ACCOUNT_API_SUBDOMAIN = "api"
ACCOUNT_MANAGER_SUBDOMAIN = "account"
ACCOUNT_COMPANY_NAME = "Smarter"
ACCOUNT_CUSTOMER_SUPPORT_EMAIL = "support@smarter.sh"
ACCOUNT_CONTACT_EMAIL = "contact@smarter.sh"
ACCOUNT_CUSTOMER_SUPPORT_PHONE = "+1 (512) 833-6955"


# This is a custom attribute that can be added to the request
# to indicate that the request is an internal API request. This
# is used to bypass DRF authentication and permission checks in the API views.
ACCOUNT_IS_INTERNAL_API_REQUEST = "smarter_is_internal_api_request"

# Default cache expiration expressed in seconds for Redis based Django caching.
ACCOUNT_DEFAULT_CACHE_TIMEOUT = 60 * 5  # 5 minutes

# Default maximum lifetime for Account Manager API keys in days.
ACCOUNT_API_KEY_MAX_LIFETIME_DAYS = 365 * 3  # 3 years


HERE = os.path.abspath(os.path.dirname(__file__))  # account/account/common
PROJECT_ROOT = str(Path(HERE).parent)  # account/account
PYTHON_ROOT = str(Path(PROJECT_ROOT).parent)  # account
REPO_ROOT = str(Path(PYTHON_ROOT).parent)  # ./
TERRAFORM_ROOT = str(Path(PROJECT_ROOT).parent.parent)  # ./

TERRAFORM_TFVARS = os.path.join(TERRAFORM_ROOT, "terraform.tfvars")
if not os.path.exists(TERRAFORM_TFVARS):
    TERRAFORM_TFVARS = os.path.join(PROJECT_ROOT, "terraform.tfvars")

TFVARS = {}
IS_USING_TFVARS = False

try:
    with open(TERRAFORM_TFVARS, encoding="utf-8") as f:
        TFVARS = hcl2.load(f)
    IS_USING_TFVARS = True
except FileNotFoundError:
    logger.info("No terraform.tfvars file found. Using default values.")


def load_version() -> Dict[str, str]:
    """Stringify the __version__ module."""
    version_file_path = os.path.join(PROJECT_ROOT, "__version__.py")
    spec = importlib.util.spec_from_file_location("__version__", version_file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load version file: {version_file_path}")
    version_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(version_module)
    return version_module.__dict__


VERSION = load_version()


# pylint: disable=too-few-public-methods
class AMEnvironments:
    """A class representing the fixed set environments for the Account Manager API."""

    LOCAL = "local"
    ALPHA = "alpha"
    BETA = "beta"
    NEXT = "next"
    PROD = "prod"
    all = [LOCAL, ALPHA, BETA, NEXT, PROD]
    aws_environments = [ALPHA, BETA, NEXT, PROD]
