# pylint: disable=E1101
"""Constants for the Account Manager."""

import logging
import os
from pathlib import Path

import hcl2

logger = logging.getLogger(__name__)

ACCOUNT_ACCOUNT_NUMBER = "3141-5926-5359"
ACCOUNT_API_SUBDOMAIN = "api"
ACCOUNT_MANAGER_SUBDOMAIN = "am"
ACCOUNT_COMPANY_NAME = "Smarter"
ACCOUNT_CUSTOMER_SUPPORT_EMAIL = "support@smarter.sh"
ACCOUNT_CUSTOMER_SUPPORT_PHONE = "+1 (512) 833-6955"


# Default cache expiration expressed in seconds for Redis based Django caching.
ACCOUNT_DEFAULT_CACHE_TIMEOUT = 60 * 5  # 5 minutes

# Default maximum lifetime for Account Manager API keys in days.
ACCOUNT_API_KEY_MAX_LIFETIME_DAYS = 365 * 3  # 3 years


HERE = os.path.abspath(os.path.dirname(__file__))  # am/am/common
PROJECT_ROOT = str(Path(HERE).parent)  # am/am
TERRAFORM_ROOT = str(Path(PROJECT_ROOT).parent.parent)  # ./

TERRAFORM_TFVARS = os.path.join(TERRAFORM_ROOT, "terraform.tfvars")
if not os.path.exists(TERRAFORM_TFVARS):
    TERRAFORM_TFVARS = os.path.join(PROJECT_ROOT, "terraform.tfvars")


def load_tfvars(path: str) -> dict:
    """
    Read a Terraform variables file.

    :param path: The path of a ``terraform.tfvars`` file.
    :type path: str
    :returns: The variables in the file, or an empty dict if the file does not exist.
    :rtype: dict
    """
    # python-hcl2 8 keeps the quotes of a string value unless asked not to: "example.com", not example.com.
    options = hcl2.SerializationOptions(strip_string_quotes=True, with_comments=False)
    try:
        with open(path, encoding="utf-8") as f:
            return hcl2.load(f, serialization_options=options)
    except FileNotFoundError:
        logger.info("No terraform.tfvars file found. Using default values.")
        return {}


TFVARS = load_tfvars(TERRAFORM_TFVARS)


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
