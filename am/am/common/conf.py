# pylint: disable=no-member,no-self-argument,unused-argument,R0801
"""
Account Manager configuration settings.

This module is used to generate strongly typed settings values for the platform.
It uses the pydantic_settings library to validate the configuration values.
The configuration values are initialized according to the following
prioritization sequence:

    1. constructor
    2. `.env` file
    3. environment variables (if present, these are overridden by .env file values)
    4. defaults
"""

# -------------------- WARNING --------------------
# DO NOT IMPORT DJANGO OR ANY DJANGO MODULES. THIS
# ENTIRE MODULE SITS UPSTREAM OF DJANGO AND IS
# INTENDED TO BE USED INDEPENDENTLY OF DJANGO.
# ------------------------------------------------

# python stuff
import logging
import os  # library for interacting with the operating system
import warnings
from functools import cached_property, lru_cache
from typing import Any, List, Optional

# 3rd party stuff
import boto3  # AWS SDK for Python https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings

from am.lib.django.validators import AMValidator

# our stuff
from .const import (
    ACCOUNT_API_KEY_MAX_LIFETIME_DAYS,
    ACCOUNT_API_SUBDOMAIN,
    ACCOUNT_MANAGER_SUBDOMAIN,
    TFVARS,
    AMEnvironments,
)
from .exceptions import AMConfigurationError, AMValueError

logger = logging.getLogger(__name__)
LOCALHOST = "localhost:8000"
DEFAULT_MISSING_VALUE = "SET-ME-PLEASE"
DEFAULT_AWS_REGIONS = ["us-east-1"]
TRUE_STRINGS = ["true", "1", "t", "y", "yes"]
load_dotenv()


def bool_environment_variable(var_name: str, default: bool) -> bool:
    """
    Get a boolean environment variable.

    :param var_name: The name of the environment variable.
    :type var_name: str
    :param default: The value to return if the environment variable is not set.
    :type default: bool
    :returns: True if the variable is set to one of ``true``, ``1``, ``t``, ``y`` or ``yes``
        (case insensitive), False if it is set to anything else, and ``default`` if it is not set.
    :rtype: bool
    """
    value = os.environ.get(var_name)
    if value is None:
        return default
    return value.lower() in TRUE_STRINGS


class DjangoPermittedStorages:
    """Django permitted storage backends."""

    AWS_S3 = "storages.backends.s3boto3.S3Boto3Storage"
    FILE_SYSTEM = "django.core.files.storage.FileSystemStorage"


# pylint: disable=too-few-public-methods
class SettingsDefaults:
    """
    Default values for Settings.

    This takes care of most of what we're interested in.
    It initializes from the following prioritization sequence:
      1. environment variables
      2. tfvars
      3. defaults.
    """

    ROOT_DOMAIN = os.environ.get("ROOT_DOMAIN", TFVARS.get("root_domain", "example.com"))

    # aws auth
    AWS_PROFILE = os.environ.get("AWS_PROFILE", TFVARS.get("aws_profile", None))
    AWS_ACCESS_KEY_ID: SecretStr = SecretStr(os.environ.get("AWS_ACCESS_KEY_ID", DEFAULT_MISSING_VALUE))
    AWS_SECRET_ACCESS_KEY: SecretStr = SecretStr(os.environ.get("AWS_SECRET_ACCESS_KEY", DEFAULT_MISSING_VALUE))
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    AWS_IS_CONFIGURED = bool(
        AWS_PROFILE
        or (
            AWS_ACCESS_KEY_ID.get_secret_value() != DEFAULT_MISSING_VALUE
            and AWS_SECRET_ACCESS_KEY.get_secret_value() != DEFAULT_MISSING_VALUE
        )
    )

    DEBUG_MODE: bool = bool_environment_variable("DEBUG_MODE", bool(TFVARS.get("debug_mode", False)))
    DEVELOPER_MODE: bool = bool_environment_variable("DEVELOPER_MODE", bool(TFVARS.get("developer_mode", False)))

    DJANGO_DEFAULT_FILE_STORAGE = os.environ.get("DJANGO_DEFAULT_FILE_STORAGE", DjangoPermittedStorages.AWS_S3)
    if DJANGO_DEFAULT_FILE_STORAGE == DjangoPermittedStorages.AWS_S3 and not AWS_IS_CONFIGURED:
        DJANGO_DEFAULT_FILE_STORAGE = DjangoPermittedStorages.FILE_SYSTEM
        logger.warning(
            "AWS is not configured properly. Falling back to FileSystemStorage for Django default file storage."
        )

    ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")

    LOCAL_HOSTS = [LOCALHOST, "127.0.0.1"]
    LOCAL_HOSTS += [host + ":8000" for host in LOCAL_HOSTS]
    LOCAL_HOSTS.append("testserver")

    LOG_LEVEL: int = logging.DEBUG if DEBUG_MODE else logging.INFO

    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_MISSING_VALUE)

    SMTP_SENDER = os.environ.get("SMTP_SENDER", DEFAULT_MISSING_VALUE)
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", f"no-reply@{ROOT_DOMAIN}")
    SMTP_HOST = os.environ.get("SMTP_HOST", "email-smtp.us-east-2.amazonaws.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USE_SSL = bool_environment_variable("SMTP_USE_SSL", False)
    SMTP_USE_TLS = bool_environment_variable("SMTP_USE_TLS", True)
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", DEFAULT_MISSING_VALUE)
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", DEFAULT_MISSING_VALUE)

    STRIPE_LIVE_SECRET_KEY = os.environ.get("STRIPE_LIVE_SECRET_KEY", DEFAULT_MISSING_VALUE)
    STRIPE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", DEFAULT_MISSING_VALUE)


def get_aws_regions(region_name: str = SettingsDefaults.AWS_REGION) -> List[str]:
    """
    Return the AWS regions that ``aws_region`` may be set to.

    Asks AWS EC2 for its regions when boto3 finds credentials. Without credentials, or if
    AWS refuses the request, it returns ``DEFAULT_AWS_REGIONS``.

    :param region_name: The region of the EC2 client that lists the regions.
    :type region_name: str
    :returns: The names of the valid AWS regions.
    :rtype: List[str]
    """
    try:
        session = boto3.Session(region_name=region_name)
        if not session.get_credentials():
            return DEFAULT_AWS_REGIONS
        regions = session.client("ec2").describe_regions()
        return [region["RegionName"] for region in regions["Regions"]]
    except (BotoCoreError, ClientError) as e:
        logger.warning("could not list AWS regions, using %s: %s", DEFAULT_AWS_REGIONS, type(e).__name__)
        return DEFAULT_AWS_REGIONS


AWS_REGIONS = get_aws_regions()


# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes
class Settings(BaseSettings):
    """
    Account Manager derived settings.

    This is intended to be instantiated as
    an immutable singleton object called `am_settings`. am_settings
    contains superseding, validated, and derived settings values for the platform.

    This class implements a consistent set of rules for initializing configuration
    values from multiple sources, including environment variables, `.env` file, TFVARS,
    and default values defined in this class. It additionally ensures that all
    configuration values are strongly typed and validated.

    Where applicable, am_settings supersede Django settings values. That is,
    am_settings should be used in preference to Django settings wherever
    possible. Django settings are initialized from am_settings values where
    applicable.

    Notes:
    -----------------
    - am_settings values are immutable after instantiation.
    - Every property/attribute in am_settings has a value.
    - Sensitive values are stored as pydantic SecretStr types.
    - am_settings values are initialized according to the following prioritization sequence:
        1. constructor. This is discouraged. prefer to use .env file or environment variables.
        2. SettingsDefaults
        3. `.env` file
        4. environment variables. If present and not already consumed by SettingsDefaults, these are overridden by .env file values.
        5. default values defined in this class.
    - am_settings values should be accessed via the am_settings singleton instance when possible.
    """

    # pylint: disable=too-few-public-methods
    class Config:
        """Pydantic configuration."""

        frozen = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        logger.setLevel(SettingsDefaults.LOG_LEVEL)
        logger.debug("Settings initialized")

    debug_mode: bool = Field(
        SettingsDefaults.DEBUG_MODE,
        description="True if debug mode is enabled. This enables verbose logging and other debug features.",
    )
    default_missing_value: str = Field(
        DEFAULT_MISSING_VALUE,
        description="Default missing value placeholder string. Used for consistency across settings.",
        examples=["SET-ME-PLEASE"],
    )

    # new in 0.13.26
    # True if developer mode is enabled. Used as a means to configure a production
    # Docker container to run locally for student use.
    developer_mode: bool = Field(
        SettingsDefaults.DEVELOPER_MODE,
        description="True if developer mode is enabled. Used as a means to configure a production Docker container to run locally for student use.",
    )
    django_default_file_storage: str = Field(
        SettingsDefaults.DJANGO_DEFAULT_FILE_STORAGE,
        description="The default Django file storage backend.",
        examples=["storages.backends.s3boto3.S3Boto3Storage", "django.core.files.storage.FileSystemStorage"],
    )
    log_level: int = Field(
        SettingsDefaults.LOG_LEVEL,
        description="The logging level based on Python logging levels: logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL",
        examples=[logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL],
    )
    aws_profile: Optional[str] = Field(
        SettingsDefaults.AWS_PROFILE,
        description="The AWS profile to use for authentication. If present, this will take precedence over AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
        examples=["default", "smarter-profile"],
    )
    aws_access_key_id: SecretStr = Field(
        SettingsDefaults.AWS_ACCESS_KEY_ID,
        description="The AWS access key ID for authentication. Used if AWS_PROFILE is not set. Masked by pydantic SecretStr.",
        examples=["^AKIA[0-9A-Z]{16}$"],
    )
    aws_secret_access_key: SecretStr = Field(
        SettingsDefaults.AWS_SECRET_ACCESS_KEY,
        description="The AWS secret access key for authentication. Used if AWS_PROFILE is not set. Masked by pydantic SecretStr.",
        examples=["^[0-9a-zA-Z/+]{40}$"],
    )
    aws_regions: List[str] = Field(
        AWS_REGIONS,
        description="A list of AWS regions considered valid.",
        examples=["us-east-1", "us-west-2", "eu-west-1"],
    )
    aws_region: str = Field(
        SettingsDefaults.AWS_REGION,
        description="The single AWS region in which all AWS service clients will operate.",
        examples=["us-east-1", "us-west-2", "eu-west-1"],
    )
    aws_is_configured: bool = Field(
        SettingsDefaults.AWS_IS_CONFIGURED,
        description="True if AWS is configured. This is determined by the presence of either AWS_PROFILE or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
    )
    environment: str = Field(
        SettingsDefaults.ENVIRONMENT,
        description="The deployment environment. eg 'alpha', 'beta', 'prod', 'local', etc.",
        examples=AMEnvironments.all,
    )
    local_hosts: List[str] = Field(
        SettingsDefaults.LOCAL_HOSTS,
        description="A list of hostnames considered local for development and testing purposes.",
        examples=SettingsDefaults.LOCAL_HOSTS,
    )
    root_domain: str = Field(
        SettingsDefaults.ROOT_DOMAIN,
        description="The root internet domain name. eg 'example.com'",
        examples=["example.com"],
    )
    stripe_live_secret_key: Optional[str] = Field(
        SettingsDefaults.STRIPE_LIVE_SECRET_KEY,
        description="DEPRECATED: The secret key for Stripe live environment.",
        examples=["sk_live_xxxxxxxxxxxxxxxxxxxxxxxx"],
    )
    stripe_test_secret_key: Optional[str] = Field(
        SettingsDefaults.STRIPE_TEST_SECRET_KEY,
        description="DEPRECATED: The secret key for Stripe test environment.",
        examples=["sk_test_xxxxxxxxxxxxxxxxxxxxxxxx"],
    )

    secret_key: Optional[str] = Field(
        SettingsDefaults.SECRET_KEY,
        description="The Django secret key for cryptographic signing.",
        examples=["your-django-secret-key"],
    )

    smtp_sender: Optional[str] = Field(
        SettingsDefaults.SMTP_SENDER,
        description="The sender email address for SMTP emails.",
        examples=["sender@example.com"],
    )
    smtp_from_email: Optional[str] = Field(
        SettingsDefaults.SMTP_FROM_EMAIL,
        description="The from email address for SMTP emails.",
        examples=["from@example.com"],
    )
    smtp_host: Optional[str] = Field(
        SettingsDefaults.SMTP_HOST,
        description="The SMTP host address for sending emails.",
        examples=["smtp.example.com"],
    )
    smtp_password: Optional[str] = Field(
        SettingsDefaults.SMTP_PASSWORD,
        description="The SMTP password for authentication.",
        examples=["your-smtp-password"],
    )
    smtp_port: Optional[int] = Field(
        SettingsDefaults.SMTP_PORT,
        description="The SMTP port for sending emails.",
        examples=[25, 465, 587],
    )
    smtp_use_ssl: Optional[bool] = Field(
        SettingsDefaults.SMTP_USE_SSL,
        description="Whether to use SSL for SMTP connections.",
        examples=[True, False],
    )
    smtp_use_tls: Optional[bool] = Field(
        SettingsDefaults.SMTP_USE_TLS,
        description="Whether to use TLS for SMTP connections.",
        examples=[True, False],
    )
    smtp_username: Optional[str] = Field(
        SettingsDefaults.SMTP_USERNAME,
        description="The SMTP username for authentication.",
        examples=["your-smtp-username"],
    )

    @cached_property
    def smtp_is_configured(self) -> bool:
        """
        Return True if SMTP is configured.

        All required smtp fields must be set.

        Example:
            >>> print(am_settings.smtp_is_configured)
            True

        See Also:
            - am_settings.smtp_host
            - am_settings.smtp_port
            - am_settings.smtp_username
            - am_settings.smtp_password
            - am_settings.smtp_from_email
        """
        required_fields = [
            self.smtp_host,
            self.smtp_port,
            self.smtp_username,
            self.smtp_password,
            self.smtp_from_email,
        ]
        return all(field not in [None, "", DEFAULT_MISSING_VALUE] for field in required_fields)

    @cached_property
    def environment_is_local(self) -> bool:
        """
        Return True if the environment is local.

        Example:
            >>> print(am_settings.environment_is_local)
            True

        See Also:
            - am_settings.environment
            - AMEnvironments()
        """
        return self.environment == AMEnvironments.LOCAL

    @cached_property
    def environment_cdn_domain(self) -> str:
        """
        Return the CDN domain based on the environment domain.

        Examples:
            >>> print(am_settings.environment_cdn_domain)
            'cdn.alpha.am.example.com'

        See Also:
            - am_settings.am_subdomain
            - am_settings.environment_domain
            - am_settings.environment
            - AMEnvironments()
        """
        if self.environment == AMEnvironments.LOCAL:
            return f"cdn.{AMEnvironments.ALPHA}.{self.am_subdomain}.{self.root_domain}"
        return f"cdn.{self.environment_domain}"

    @property
    def am_subdomain(self) -> str:
        """
        Return the Account Manager subdomain.

        Example:
            >>> print(am_settings.am_subdomain)
            'am'

        See Also:
            - ACCOUNT_MANAGER_SUBDOMAIN
        """
        return ACCOUNT_MANAGER_SUBDOMAIN

    @cached_property
    def am_domain(self) -> str:
        """
        Return the base Account Manager domain name.

        Example:
            >>> print(am_settings.am_domain)
            'am.example.com'

        See Also:
            - am.settings.am_subdomain
            - am_settings.root_domain
        """
        return f"{self.am_subdomain}.{self.root_domain}"

    @cached_property
    def am_api_domain(self) -> str:
        """
        Return the Account Manager API base domain name.

        Example:
            >>> print(am_settings.am_api_domain)
            'api.am.example.com'
        See Also:
            - am.settings.api_subdomain
            - am_settings.root_domain
        """
        return f"{self.api_subdomain}.{self.am_subdomain}.{self.root_domain}"

    @property
    def platform_subdomain(self) -> str:
        """
        Return the platform subdomain.

        Example:
            >>> print(am_settings.platform_subdomain)
            'platform'
        """
        return "platform"

    @property
    def platform_domain(self) -> str:
        """
        Return the platform domain name.

        Example:
            >>> print(am_settings.platform_domain)
            'platform.example.com'

        See Also:
            - am_settings.platform_subdomain
            - am_settings.root_domain
        """
        return f"{self.platform_subdomain}.{self.root_domain}"

    @cached_property
    def environment_domain(self) -> str:
        """
        Return the complete domain name, including environment prefix if applicable.

        Examples:
            >>> print(am_settings.environment_domain)
            'alpha.am.example.com'
            >>> print(am_settings.environment_domain)
            'am.localhost:8000'

        See Also:
            - am_settings.am_domain
            - AMEnvironments()
            - self.environment
        """
        if self.environment == AMEnvironments.PROD:
            return self.am_domain
        if self.environment == AMEnvironments.LOCAL:
            return f"{self.am_subdomain}.{LOCALHOST}"
        return f"{self.environment}.{self.am_domain}"

    @cached_property
    def environment_url(self) -> str:
        """
        Return the environment URL, derived from the environment domain.

        Example:
            >>> print(am_settings.environment_url)
            https://alpha.am.example.com/

        Raises:
            AMValueError: If the constructed URL is invalid.

        See Also:
            - AMValidator.urlify()
            - am_settings.environment_domain
            - am_settings.environment
        """
        return AMValidator.urlify(self.environment_domain, environment=self.environment)

    @property
    def api_subdomain(self) -> str:
        """
        Return the API subdomain.

        Example:
            >>> print(am_settings.api_subdomain)
            'api'

        See Also:
            - ACCOUNT_API_SUBDOMAIN
        """
        return ACCOUNT_API_SUBDOMAIN

    @cached_property
    def environment_api_domain(self) -> str:
        """
        Return the API domain name for the current environment.

        Example:
            >>> print(am_settings.environment_api_domain)
            'alpha.api.am.example.com'
            >>> print(am_settings.environment_api_domain)
            'api.am.localhost:8000'

        See Also:
            - AMEnvironments()
            - ACCOUNT_API_SUBDOMAIN
        """
        if self.environment == AMEnvironments.PROD:
            return self.am_api_domain
        if self.environment == AMEnvironments.LOCAL:
            return f"{self.api_subdomain}.{self.am_subdomain}.{LOCALHOST}"
        return f"{self.environment}.{self.am_api_domain}"

    @cached_property
    def environment_api_url(self) -> str:
        """
        Creates a valid url from am_settings.environment_api_domain.

        Example:
            >>> print(am_settings.environment_api_url)
            'https://alpha.api.am.example.com/'

        Raises:
            AMValueError: If the constructed URL is invalid.

        See Also:
            - AMValidator.urlify()
            - am_settings.environment_api_domain
            - am_settings.environment
        """
        return AMValidator.urlify(self.environment_api_domain, environment=self.environment)

    @cached_property
    def aws_s3_bucket_name(self) -> str:
        """
        Returns the AWS S3 bucket name for the current environment, which.

        is the environment domain.

        Example:
            >>> print(am_settings.aws_s3_bucket_name)
            'alpha.am.smarter.sh'

        Note:
            In local environments, this returns the alpha environment's bucket as a proxy.

        See Also:
            - am_settings.am_domain
            - AMEnvironments()
            - am_settings.environment_domain
        """
        if self.environment == AMEnvironments.LOCAL:
            return f"{AMEnvironments.ALPHA}.{self.am_domain}"
        return self.environment_domain

    @cached_property
    def smarter_api_key_max_lifetime_days(self) -> int:
        """Maximum lifetime for Account Manager API keys in days.

        Returns:
            int: The number of days.

        Example:
            >>> print(am_settings.smarter_api_key_max_lifetime_days)
            1095

        Warning:
            Changing this value requires a rebuild/redeploy.
            Expired API keys still function but will log warnings.

        See Also:
            - ACCOUNT_API_KEY_MAX_LIFETIME_DAYS
        """
        return ACCOUNT_API_KEY_MAX_LIFETIME_DAYS

    @field_validator("aws_profile")
    def validate_aws_profile(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `aws_profile` field.

        Uses SettingsDefaults if no value is received.

        Args:
            v (Optional[str]): The AWS profile value to validate.

        Returns:
            Optional[str]: The validated AWS profile.
        """
        if v is None or v == "":
            return SettingsDefaults.AWS_PROFILE
        return v

    @field_validator("aws_access_key_id")
    def validate_aws_access_key_id(cls, v: SecretStr, values: ValidationInfo) -> SecretStr:
        """Validates the `aws_access_key_id` field.

        Uses SettingsDefaults if no value is received, or if an aws_profile
        other than the default one is set.

        Args:
            v (SecretStr): The AWS access key ID value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Returns:
            SecretStr: The validated AWS access key ID.
        """
        if v.get_secret_value() == "":
            return SettingsDefaults.AWS_ACCESS_KEY_ID
        aws_profile = values.data.get("aws_profile", None)
        if aws_profile and aws_profile != SettingsDefaults.AWS_PROFILE:
            logger.warning("aws_access_key_id is being ignored. using aws_profile %s.", aws_profile)
            return SettingsDefaults.AWS_ACCESS_KEY_ID
        return v

    @field_validator("aws_secret_access_key")
    def validate_aws_secret_access_key(cls, v: SecretStr, values: ValidationInfo) -> SecretStr:
        """Validates the `aws_secret_access_key` field.

        Uses SettingsDefaults if no value is received, or if an aws_profile
        other than the default one is set.

        Args:
            v (SecretStr): The AWS secret access key value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Returns:
            SecretStr: The validated AWS secret access key.
        """
        if v.get_secret_value() == "":
            return SettingsDefaults.AWS_SECRET_ACCESS_KEY
        aws_profile = values.data.get("aws_profile", None)
        if aws_profile and aws_profile != SettingsDefaults.AWS_PROFILE:
            logger.warning("aws_secret_access_key is being ignored. using aws_profile %s.", aws_profile)
            return SettingsDefaults.AWS_SECRET_ACCESS_KEY
        return v

    @field_validator("aws_region")
    def validate_aws_region(cls, v: str, values: ValidationInfo) -> str:
        """Validates the `aws_region` field.

        Uses SettingsDefaults if no value is received.

        Args:
            v (str): The AWS region value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Raises:
            AMValueError: If the region is not one of aws_regions.

        Returns:
            str: The validated AWS region.
        """
        valid_regions = values.data.get("aws_regions", DEFAULT_AWS_REGIONS)
        if v == "":
            return SettingsDefaults.AWS_REGION
        if v not in valid_regions:
            raise AMValueError(f"aws_region {v} not in aws_regions: {valid_regions}")
        return v

    @field_validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validates the `environment` field.

        Args:
            v (str): The environment value to validate.

        Returns:
            str: The validated environment, or the default one if empty.
        """
        if v == "":
            return SettingsDefaults.ENVIRONMENT
        return v

    @field_validator("root_domain")
    def validate_root_domain(cls, v: str) -> str:
        """
        Validates the `root_domain` field.

        Args:
            v (str): The root domain value to validate.

        Returns:
            str: The validated root domain, or the default one if empty.
        """
        if v == "":
            return SettingsDefaults.ROOT_DOMAIN
        return v

    @field_validator("stripe_live_secret_key")
    def check_stripe_live_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `stripe_live_secret_key` field.

        Args:
            v (Optional[str]): The Stripe live secret key to validate.

        Returns:
            str: The validated Stripe live secret key.
        """
        if v is None or v == "":
            warnings.warn(
                "The 'stripe_live_secret_key' field is deprecated and will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            return SettingsDefaults.STRIPE_LIVE_SECRET_KEY
        return v

    @field_validator("stripe_test_secret_key")
    def check_stripe_test_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `stripe_test_secret_key` field.

        Args:
            v (Optional[str]): The Stripe test secret key to validate.
        Returns:
            str: The validated Stripe test secret key.
        """
        if v is None or v == "":
            warnings.warn(
                "The 'stripe_test_secret_key' field is deprecated and will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            return SettingsDefaults.STRIPE_TEST_SECRET_KEY
        return v

    @field_validator("secret_key")
    def check_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `secret_key` field.

        Args:
            v (Optional[str]): The secret key value to validate.
        Returns:
            str: The validated secret key.
        """
        if v is None or v == "":
            return SettingsDefaults.SECRET_KEY
        return v

    @field_validator("smtp_sender")
    def check_smtp_sender(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_sender` field.

        Args:
            v (Optional[str]): The SMTP sender email address to validate.

        Returns:
            Optional[str]: The validated SMTP sender, or the default one if empty.
        """
        if v is None or v == "":
            return SettingsDefaults.SMTP_SENDER
        return v

    @field_validator("smtp_from_email")
    def check_smtp_from_email(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_from_email` field.

        Args:
            v (Optional[str]): The SMTP from email address to validate.

        Raises:
            AMValueError: If the value is not a valid email address.

        Returns:
            Optional[str]: The validated SMTP from email address.
        """
        if v is None or v == "":
            return SettingsDefaults.SMTP_FROM_EMAIL
        AMValidator.validate_email(v)
        return v

    @field_validator("smtp_host")
    def check_smtp_host(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_host` field.

        Args:
            v (Optional[str]): The SMTP host to validate.

        Returns:
            Optional[str]: The validated SMTP host, or the default one if empty.
        """
        if v is None or v == "":
            return SettingsDefaults.SMTP_HOST
        return v

    @field_validator("smtp_password")
    def check_smtp_password(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_password` field.

        Args:
            v (Optional[str]): The SMTP password to validate.

        Returns:
            Optional[str]: The validated SMTP password.
        """
        if v is None or v == "":
            return SettingsDefaults.SMTP_PASSWORD
        return v

    @field_validator("smtp_port")
    def check_smtp_port(cls, v: Optional[int]) -> int:
        """Validates the `smtp_port` field.

        Args:
            v (Optional[int]): The SMTP port to validate.

        Raises:
            AMValueError: If the port is not between 1 and 65535.

        Returns:
            int: The validated SMTP port.
        """
        if v is None:
            return SettingsDefaults.SMTP_PORT
        if not 1 <= v <= 65535:
            raise AMValueError("Invalid port number")
        return v

    @field_validator("smtp_use_ssl")
    def check_smtp_use_ssl(cls, v: Optional[bool]) -> bool:
        """Validates the `smtp_use_ssl` field.

        Args:
            v (Optional[bool]): The SMTP use SSL flag to validate.

        Returns:
            bool: The validated SMTP use SSL flag.
        """
        if v is None:
            return SettingsDefaults.SMTP_USE_SSL
        return v

    @field_validator("smtp_use_tls")
    def check_smtp_use_tls(cls, v: Optional[bool]) -> bool:
        """Validates the `smtp_use_tls` field.

        Args:
            v (Optional[bool]): The SMTP use TLS flag to validate.
        Returns:
            bool: The validated SMTP use TLS flag.
        """
        if v is None:
            return SettingsDefaults.SMTP_USE_TLS
        return v

    @field_validator("smtp_username")
    def check_smtp_username(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_username` field.

        Args:
            v (Optional[str]): The SMTP username to validate.

        Returns:
            Optional[str]: The validated SMTP username.
        """
        if v is None or v == "":
            return SettingsDefaults.SMTP_USERNAME
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton settings instance."""
    try:
        return Settings()
    except ValidationError as e:
        raise AMConfigurationError("Invalid configuration: " + str(e)) from e


am_settings = get_settings()
logger.info("am_settings Singleton is initialized.")
