# pylint: disable=no-member,no-self-argument,unused-argument,R0801,too-many-lines
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

The Settings class also provides a dump property that returns a dictionary of all
configuration values. This is useful for debugging and logging.
"""

# -------------------- WARNING --------------------
# DO NOT IMPORT DJANGO OR ANY DJANGO MODULES. THIS
# ENTIRE MODULE SITS UPSTREAM OF DJANGO AND IS
# INTENDED TO BE USED INDEPENDENTLY OF DJANGO.
# ------------------------------------------------

# python stuff
import base64
import logging
import os  # library for interacting with the operating system
import re
import warnings
from functools import cached_property, lru_cache
from typing import Any, List, Optional, Tuple, Union

# 3rd party stuff
# pylint: disable=C0301
import boto3  # AWS SDK for Python https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
from botocore.exceptions import NoCredentialsError, ProfileNotFound
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
    VERSION,
    AMEnvironments,
)
from .exceptions import AMConfigurationError, AMValueError


logger = logging.getLogger(__name__)
LOCALHOST = "localhost:8000"
DEFAULT_MISSING_VALUE = "SET-ME-PLEASE"
TFVARS = TFVARS or {}
DOT_ENV_LOADED = load_dotenv()


def recursive_sort_dict(d):
    """Recursively sort a dictionary by key."""
    return {k: recursive_sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(d.items())}


def bool_environment_variable(var_name: str, default: bool) -> bool:
    """Get a boolean environment variable"""
    value = os.environ.get(var_name)
    if value is None:
        return default
    return value.lower() in ["true", "1", "t", "y", "yes"]


def get_semantic_version() -> str:
    """
    Return the semantic version number.

    Example valid values of __version__.py are:
    0.1.07
    0.1.07-alpha.1
    0.1.07-beta.1
    0.1.07-next.1
    0.1.07-next.2
    0.1.07-next.123456
    0.1.07-next-major.1
    0.1.07-next-major.2
    0.1.07-next-major.123456

    Note:
    - pypi does not allow semantic version numbers to contain a dash.
    - pypi does not allow semantic version numbers to contain a 'v' prefix.
    - pypi does not allow semantic version numbers to contain a 'next' suffix.
    """
    if not isinstance(VERSION, dict):
        return "unknown"

    version = VERSION.get("__version__")
    if not version:
        return "unknown"
    version = re.sub(r"-next\.\d+", "", version)
    return re.sub(r"-next-major\.\d+", "", version)


class DjangoPermittedStorages:
    """Django permitted storage backends"""

    AWS_S3 = "storages.backends.s3boto3.S3Boto3Storage"
    FILE_SYSTEM = "django.core.files.storage.FileSystemStorage"


# pylint: disable=too-few-public-methods
class SettingsDefaults:
    """
    Default values for Settings. This takes care of most of what we're interested in.
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

    AWS_EKS_CLUSTER_NAME = os.environ.get(
        "AWS_EKS_CLUSTER_NAME", TFVARS.get("aws_eks_cluster_name", "apps-hosting-service")
    )
    AWS_RDS_DB_INSTANCE_IDENTIFIER = os.environ.get("AWS_RDS_DB_INSTANCE_IDENTIFIER", "apps-hosting-service")
    DEBUG_MODE: bool = bool(os.environ.get("DEBUG_MODE", TFVARS.get("debug_mode", False)))
    DEVELOPER_MODE: bool = bool(os.environ.get("DEVELOPER_MODE", TFVARS.get("developer_mode", False)))

    DJANGO_DEFAULT_FILE_STORAGE = os.environ.get("DJANGO_DEFAULT_FILE_STORAGE", DjangoPermittedStorages.AWS_S3)
    if DJANGO_DEFAULT_FILE_STORAGE == DjangoPermittedStorages.AWS_S3 and not AWS_IS_CONFIGURED:
        DJANGO_DEFAULT_FILE_STORAGE = DjangoPermittedStorages.FILE_SYSTEM
        logger.warning(
            "AWS is not configured properly. Falling back to FileSystemStorage for Django default file storage."
        )

    ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")

    FERNET_ENCRYPTION_KEY: str = os.environ.get("FERNET_ENCRYPTION_KEY", DEFAULT_MISSING_VALUE)

    LOCAL_HOSTS = [LOCALHOST, "127.0.0.1"]
    LOCAL_HOSTS += [host + ":8000" for host in LOCAL_HOSTS]
    LOCAL_HOSTS.append("testserver")

    LOG_LEVEL: int = logging.DEBUG if DEBUG_MODE else logging.INFO

    LOGO: str = os.environ.get("OPENAI_API_ORGANIZATION", "https://cdn.am.smarter.sh/images/logo/smarter-crop.png")
    MAILCHIMP_API_KEY: SecretStr = SecretStr(os.environ.get("MAILCHIMP_API_KEY", DEFAULT_MISSING_VALUE))
    MAILCHIMP_LIST_ID = os.environ.get("MAILCHIMP_LIST_ID", DEFAULT_MISSING_VALUE)

    MARKETING_SITE_URL: str = os.environ.get("OPENAI_API_ORGANIZATION", f"https://{ROOT_DOMAIN}")

    SHARED_RESOURCE_IDENTIFIER = os.environ.get(
        "SHARED_RESOURCE_IDENTIFIER", TFVARS.get("shared_resource_identifier", "am")
    )

    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_MISSING_VALUE)

    SMTP_SENDER = os.environ.get("SMTP_SENDER", DEFAULT_MISSING_VALUE)
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", f"no-reply@{ROOT_DOMAIN}")
    SMTP_HOST = os.environ.get("SMTP_HOST", "email-smtp.us-east-2.amazonaws.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USE_SSL = bool(os.environ.get("SMTP_USE_SSL", False))
    SMTP_USE_TLS = bool(os.environ.get("SMTP_USE_TLS", True))
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", DEFAULT_MISSING_VALUE)
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", DEFAULT_MISSING_VALUE)

    STRIPE_LIVE_SECRET_KEY = os.environ.get("STRIPE_LIVE_SECRET_KEY", DEFAULT_MISSING_VALUE)
    STRIPE_TEST_SECRET_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY", DEFAULT_MISSING_VALUE)

    @classmethod
    def to_dict(cls):
        """Convert SettingsDefaults to dict"""
        return {
            key: value
            for key, value in SettingsDefaults.__dict__.items()
            if not key.startswith("__") and not callable(key) and key != "to_dict"
        }


class Services:
    """Services enabled for this solution. This is intended to be permanently read-only"""

    # enabled
    AWS_CLI = ("aws-cli", True)
    AWS_ROUTE53 = ("route53", True)
    AWS_S3 = ("s3", True)
    AWS_EC2 = ("ec2", True)
    AWS_IAM = ("iam", True)
    AWS_CLOUDWATCH = ("cloudwatch", True)
    AWS_SES = ("ses", True)
    AWS_RDS = ("rds", True)
    AWS_EKS = ("eks", True)

    # disabled
    AWS_LAMBDA = ("lambda", False)
    AWS_APIGATEWAY = ("apigateway", False)
    AWS_SNS = ("sns", False)
    AWS_SQS = ("sqs", False)
    AWS_REKOGNITION = ("rekognition", False)
    AWS_DYNAMODB = ("dynamodb", False)

    @classmethod
    def is_connected_to_aws(cls):
        return bool(boto3.Session().get_credentials())

    @classmethod
    def enabled(cls, service: Union[str, Tuple[str, bool]]) -> bool:
        """Is the service enabled?"""
        if not cls.is_connected_to_aws():
            return False
        if isinstance(service, tuple):
            service = service[0]
        return service in cls.enabled_services()

    @classmethod
    def raise_error_on_disabled(cls, service: Union[str, Tuple[str, bool]]) -> None:
        """Raise an error if the service is disabled"""
        if not cls.enabled(service):
            if SettingsDefaults.AWS_IS_CONFIGURED:
                raise AMConfigurationError(f"{service} is not enabled. See conf.Services")
            else:
                logger.warning("AWS is not configured. %s is not enabled.", service)

    @classmethod
    def to_dict(cls):
        """Convert Services to dict"""
        return {
            key: value
            for key, value in Services.__dict__.items()
            if not key.startswith("__")
            and not callable(key)
            and key not in ["enabled", "raise_error_on_disabled", "to_dict", "enabled_services"]
        }

    @classmethod
    def enabled_services(cls) -> List[str]:
        """Return a list of enabled services"""
        return [
            getattr(cls, key)[0]
            for key in dir(cls)
            if not key.startswith("__")
            and not callable(getattr(cls, key))
            and key not in ["enabled", "raise_error_on_disabled", "to_dict", "enabled_services"]
            and getattr(cls, key)[1] is True
        ]


AWS_REGIONS = ["us-east-1"]
if Services.enabled(Services.AWS_EC2):
    try:
        ec2 = boto3.Session(region_name=SettingsDefaults.AWS_REGION).client("ec2")
        regions = ec2.describe_regions()
        AWS_REGIONS = [region["RegionName"] for region in regions["Regions"]]
    except (ProfileNotFound, NoCredentialsError):
        logger.warning("could not initialize ec2 client")


def empty_str_to_bool_default(v: str, default: bool) -> bool:
    """Convert empty string to default boolean value"""
    if v in [None, ""]:
        return default
    return v.lower() in ["true", "1", "t", "y", "yes"]


def empty_str_to_int_default(v: str, default: int) -> int:
    """Convert empty string to default integer value"""
    if v in [None, ""]:
        return default
    try:
        return int(v)
    except ValueError:
        return default


# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes
class Settings(BaseSettings):
    """
    Account Manager derived settings. This is intended to be instantiated as
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
    - The dump property returns a dictionary of all configuration values.
    - am_settings values should be accessed via the am_settings singleton instance when possible.
    """

    # pylint: disable=too-few-public-methods
    class Config:
        """Pydantic configuration"""

        frozen = True

    _dump: dict

    # pylint: disable=too-many-branches,too-many-statements
    def __init__(self, **data: Any):  # noqa: C901
        super().__init__(**data)

        logger.setLevel(SettingsDefaults.LOG_LEVEL)

        logger.debug("Settings initialized")

    shared_resource_identifier: str = Field(
        SettingsDefaults.SHARED_RESOURCE_IDENTIFIER,
        description="Account Manager 1-word identifier to be used when naming any shared resource.",
        examples=["am", "mycompany", "myproject"],
    )
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
    aws_eks_cluster_name: str = Field(
        SettingsDefaults.AWS_EKS_CLUSTER_NAME,
        description="The name of the AWS EKS cluster used for hosting applications.",
        examples=["apps-hosting-service"],
    )
    aws_db_instance_identifier: str = Field(
        SettingsDefaults.AWS_RDS_DB_INSTANCE_IDENTIFIER,
        description="The RDS database instance identifier used for the environment's primary database.",
        examples=["apps-hosting-service"],
    )
    environment: str = Field(
        SettingsDefaults.ENVIRONMENT,
        description="The deployment environment. eg 'alpha', 'beta', 'prod', 'local', etc.",
        examples=AMEnvironments.all,
    )
    fernet_encryption_key: str = Field(
        SettingsDefaults.FERNET_ENCRYPTION_KEY,
        description="The Fernet encryption key used for encrypting Account Manager Secrets data.",
        examples=["gAAAAABh..."],
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
    init_info: Optional[str] = Field(
        None,
    )
    logo: Optional[str] = Field(SettingsDefaults.LOGO)
    mailchimp_api_key: Optional[SecretStr] = Field(SettingsDefaults.MAILCHIMP_API_KEY)
    mailchimp_list_id: Optional[str] = Field(SettingsDefaults.MAILCHIMP_LIST_ID)
    marketing_site_url: Optional[str] = Field(SettingsDefaults.MARKETING_SITE_URL)
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
        Return True if SMTP is configured. All required smtp fields must be set.

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
    def protocol(self) -> str:
        """
        Return the protocol: http or https.

        Example:
            >>> print(am_settings.protocol)
            'https'

        See Also:
            - am_settings.environment
            - AMEnvironments()
        """
        if self.environment in AMEnvironments.aws_environments:
            return "https"
        return "http"

    @property
    def data_directory(self) -> str:
        """
        Return the path to the data directory:

        Example:
            >>> print(am_settings.data_directory)
            '/home/am_user/data'

        Note:
            This is based on the Dockerfile located in the root of the repository.
            See https://github.com/smarter-sh/account-manager/blob/main/Dockerfile
        """
        return "/home/am_user/data"

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
            >>> print(am_settings.environment_cdn_domain)
            'cdn.localhost:8000'

        See Also:
            - am_settings.am_subdomain
            - am_settings.environment_domain
            - am_settings.environment
            - AMEnvironments()
        """
        if self.environment == AMEnvironments.LOCAL:
            return f"cdn.{AMEnvironments.ALPHA}.{self.am_subdomain}.{self.root_domain}"
        return f"cdn.{self.environment_domain}"

    @cached_property
    def environment_cdn_url(self) -> str:
        """
        Return the CDN URL for the environment.

        Example:
            >>> print(am_settings.environment_cdn_url)
            https://cdn.alpha.am.example.com
            >>> print(am_settings.environment_cdn_url)
            https://cdn.localhost:8000

        Raises:
            AMConfigurationError: If the constructed URL is invalid.

        Note:
            See https://github.com/smarter-sh/smarter-infrastructure for CDN setup details.
            Based on AWS CloudFront, AWS S3 and AWS Route 53. But, there are many details
            with regard to bucket policies, CNAME setup, SSL certificates, and so forth
            that are outside the scope of this comment. Please refer to the Terraform
            infrastructure repository for more information.

        See Also:
            - AMValidator.urlify()
            - am_settings.environment_cdn_domain
            - am_settings.environment
        """
        if self.environment == AMEnvironments.LOCAL:
            retval = AMValidator.urlify(self.environment_cdn_domain, environment=AMEnvironments.ALPHA)
        else:
            retval = AMValidator.urlify(self.environment_cdn_domain, environment=self.environment)
        if retval is None:
            raise AMConfigurationError(
                f"Invalid environment_cdn_domain: {self.environment_cdn_domain}. "
                "Please check your environment settings."
            )
        return retval

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

    @cached_property
    def am_url(self) -> str:
        """
        Return the Account Manager base URL.

        Example:
            >>> print(am_settings.am_url)
            https://am.example.com

        Raises:
            AMConfigurationError: If the constructed URL is invalid.

        See Also:
            - AMValidator.urlify()
            - am_settings.am_domain
            - am_settings.environment
        """
        retval = AMValidator.urlify(self.am_domain, environment=self.environment)
        if retval is None:
            raise AMConfigurationError(
                f"Invalid am_domain: {self.am_domain}. " "Please check your environment settings."
            )
        return retval

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
            'localhost:8000'

        See Also:
            - am_settings.am_domain
            - AMEnvironments()
            - self.environment
        """
        if self.environment == AMEnvironments.PROD:
            return self.am_domain
        if self.environment in AMEnvironments.aws_environments:
            return f"{self.environment}.{self.am_domain}"
        if self.environment == AMEnvironments.LOCAL:
            return f"{self.am_subdomain}.{LOCALHOST}"
        # default domain format
        return f"{self.environment}.{self.am_domain}"

    @cached_property
    def environment_url(self) -> str:
        """
        Return the environment URL, derived from the environment domain.

        Example:
            >>> print(am_settings.environment_url)
            https://alpha.am.example.com

        Raises:
            AMConfigurationError: If the constructed URL is invalid.

        See Also:
            - AMValidator.urlify()
            - am_settings.environment_domain
            - am_settings.environment
        """
        retval = AMValidator.urlify(self.environment_domain, environment=self.environment)
        if retval is None:
            raise AMConfigurationError(
                f"Invalid environment_domain: {self.environment_domain}. " "Please check your environment settings."
            )
        return retval

    @cached_property
    def platform_name(self) -> str:
        """
        Return the platform name, derived from the root domain.

        Example:
            >>> print(am_settings.platform_name)
            'smarter'

        See Also:
            - am_settings.root_domain
        """
        return self.root_domain.split(".")[0]

    @cached_property
    def environment_namespace(self) -> str:
        """
        Return the Kubernetes namespace for the environment.

        Example:
            >>> print(am_settings.environment_namespace)
            'smarter-am-alpha'

        See Also:
            - am_settings.am_subdomain
            - am_settings.platform_name
            - am_settings.environment
        """
        return f"{self.platform_name}-{self.am_subdomain}-{self.environment}"

    @property
    def api_subdomain(self) -> str:
        """
        Return the API subdomain.

        Example:
            >>> print(am_settings.api_subdomain)
            'api'
        return ACCOUNT_API_SUBDOMAIN
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
            'api.localhost'

        See Also:
            - am_settings.aws_environments
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
            AMConfigurationError: If the constructed URL is invalid.

        See Also:
            - AMValidator.urlify()
            - am_settings.environment_api_domain
            - am_settings.environment
        """
        retval = AMValidator.urlify(self.environment_api_domain, environment=self.environment)
        if retval is None:
            raise AMConfigurationError(
                f"Invalid environment_api_domain: {self.environment_api_domain}. "
                "Please check your environment settings."
            )
        return retval

    @cached_property
    def aws_s3_bucket_name(self) -> str:
        """
        Returns the AWS S3 bucket name for the current environment.
        The bucket name is constructed from the Account Manager shared resource identifier
        and the environment domain.

        Example:
            >>> print(am_settings.aws_s3_bucket_name)
            'alpha.am.smarter.sh'

        Note:
            In local environments, this returns 'alpha.am.smarter.sh' as a proxy.

        See Also:
            - am_settings.shared_resource_identifier
            - am_settings.am_domain
            - AMEnvironments()
            - am_settings.environment_domain
        """
        if self.environment == AMEnvironments.LOCAL:
            return f"{AMEnvironments.ALPHA}.{self.am_domain}"
        return self.environment_domain

    @cached_property
    def is_using_dotenv_file(self) -> bool:
        """
        Indicates whether a `.env` file was loaded for this instance of am_settings.

        Returns:
            bool: True if a `.env` file was loaded, False otherwise.

        Example:
            >>> print(am_settings.is_using_dotenv_file)
            True

        Note:
            This property reflects the state at the time the settings object was created.
            It would gemnerally only be expected to be True in local development environments.

        See Also:
            - DOT_ENV_LOADED
        """
        return DOT_ENV_LOADED

    @cached_property
    def environment_variables(self) -> List[str]:
        """
        Lists all environment variables.

        Returns:
            List[str]: A list of the environment variable names currently set in the OS environment
                in which the application is running (e.g., the Linux process environment,
                the operating Kubernetes Pod).
        Example:
            >>> settings.environment_variables
            [
                'PAT',
                'SECRET_KEY',
                'FERNET_ENCRYPTION_KEY',
                'ACCOUNT_MYSQL_TEST_DATABASE_SECRET_NAME',
                'ACCOUNT_MYSQL_TEST_DATABASE_PASSWORD',
                'ENVIRONMENT',
                'PYTHONPATH',
                'NODE_MAJOR',
                'DEVELOPER_MODE',
                'GEMINI_API_KEY',
                'ANTHROPIC_API_KEY',
                'COHERE_API_KEY',
                'FIREWORKS_API_KEY',
                'LLAMA_API_KEY',
                'MISTRAL_API_KEY',
                'OPENAI_API_KEY',
                'TOGETHERAI_API_KEY',
                'GOOGLE_SERVICE_ACCOUNT_B64',
                'GOOGLE_MAPS_API_KEY',
                'MAILCHIMP_API_KEY',
                'MAILCHIMP_LIST_ID',
                'PINECONE_API_KEY',
                'PINECONE_ENVIRONMENT',
                'ROOT_DOMAIN',
                'NAMESPACE',
                'MYSQL_HOST',
                'MYSQL_PORT',
                'ACCOUNT_MYSQL_DATABASE',
                'ACCOUNT_MYSQL_PASSWORD',
                'ACCOUNT_MYSQL_USERNAME',
                'MYSQL_ROOT_USERNAME',
                'MYSQL_ROOT_PASSWORD',
                'ACCOUNT_LOGIN_URL',
                'ACCOUNT_ADMIN_PASSWORD',
                'ACCOUNT_ADMIN_USERNAME',
                'ACCOUNT_DOCKER_IMAGE'
            ]

        Note:
            This list reflects the environment at the time the settings object was created.
        """
        return list(os.environ.keys())

    @cached_property
    def smarter_api_key_max_lifetime_days(self) -> int:
        """Maximum lifetime for Account Manager API keys in days.

        Returns:
            int: The number of days.

        Example:
            >>> print(am_settings.smarter_api_key_max_lifetime_days)
            90

        Warning:
            Changing this value requires a rebuild/redeploy.
            Expired API keys still function but will log warnings.

        See Also:
            - ACCOUNT_API_KEY_MAX_LIFETIME_DAYS
        """
        return ACCOUNT_API_KEY_MAX_LIFETIME_DAYS

    @cached_property
    def version(self) -> str:
        """
        Current version of the Account Manager codebase
        based on the semantic version currently persisted
        to smarter.__version__.py.

        Example:
            >>> print(am_settings.version)
            '0.13.35'

        Note:
            This value is managed by the NPM semantic-release tooling
            process and should not be modified manually. Versions are
            bumped automatically via a GitHub Actions workflow that is
            executed on merges to the main branch. The nature of the
            version bump is based on commit messages in the merge.
            See https://github.com/smarter-sh/account-manager/blob/main/docs/legacy/SEMANTIC_VERSIONING.md for more information.
        """
        return get_semantic_version()

    @field_validator("shared_resource_identifier")
    def validate_shared_resource_identifier(cls, v: Optional[str]) -> str:
        """Validates the `shared_resource_identifier` field.
        Uses SettingsDefaults if no value is received.

        Args:
            v (Optional[str]): The shared resource identifier to validate.

        Returns:
            str: The validated shared resource identifier.
        """
        if v in [None, ""]:
            return SettingsDefaults.SHARED_RESOURCE_IDENTIFIER

        if not isinstance(v, str):
            raise AMConfigurationError("shared_resource_identifier is not a str.")

        return v

    @field_validator("aws_profile")
    def validate_aws_profile(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `aws_profile` field.
        Uses SettingsDefaults if no value is received.

        Args:
            v (Optional[str]): The AWS profile value to validate.

        Returns:
            Optional[str]: The validated AWS profile.
        """
        if v in [None, ""]:
            return SettingsDefaults.AWS_PROFILE
        return v

    @field_validator("aws_access_key_id")
    def validate_aws_access_key_id(cls, v: Optional[SecretStr], values: ValidationInfo) -> SecretStr:
        """Validates the `aws_access_key_id` field.
        Uses SettingsDefaults if no value is received.


        Args:
            v (Optional[SecretStr]): The AWS access key ID value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Returns:
            SecretStr: The validated AWS access key ID.
        """
        if isinstance(v, str):
            v = SecretStr(v)
        if not isinstance(v, SecretStr):
            raise AMConfigurationError("could not convert aws_access_key_id value to SecretStr")

        if v.get_secret_value() in [None, ""]:
            return SettingsDefaults.AWS_ACCESS_KEY_ID
        aws_profile = values.data.get("aws_profile", None)
        if aws_profile and len(aws_profile) > 0 and aws_profile != SettingsDefaults.AWS_PROFILE:
            # pylint: disable=logging-fstring-interpolation
            logger.warning(f"aws_access_key_id is being ignored. using aws_profile {aws_profile}.")
            return SettingsDefaults.AWS_ACCESS_KEY_ID
        return v

    @field_validator("aws_secret_access_key")
    def validate_aws_secret_access_key(cls, v: Optional[SecretStr], values: ValidationInfo) -> SecretStr:
        """Validates the `aws_secret_access_key` field.
        Uses SettingsDefaults if no value is received.

        Args:
            v (Optional[SecretStr]): The AWS secret access key value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Returns:
            SecretStr: The validated AWS secret access key.
        """
        if isinstance(v, str):
            v = SecretStr(v)
        if not isinstance(v, SecretStr):
            raise AMConfigurationError("could not convert aws_secret_access_key value to SecretStr")
        if v.get_secret_value() in [None, ""]:
            return SettingsDefaults.AWS_SECRET_ACCESS_KEY
        aws_profile = values.data.get("aws_profile", None)
        if aws_profile and len(aws_profile) > 0 and aws_profile != SettingsDefaults.AWS_PROFILE:
            # pylint: disable=logging-fstring-interpolation
            logger.warning(f"aws_secret_access_key is being ignored. using aws_profile {aws_profile}.")
            return SettingsDefaults.AWS_SECRET_ACCESS_KEY
        return v

    @field_validator("aws_region")
    def validate_aws_region(cls, v: Optional[str], values: ValidationInfo, **kwargs) -> Optional[str]:
        """Validates the `aws_region` field.
        Uses SettingsDefaults if no value is received.

        Args:
            v (Optional[str]): The AWS region value to validate.
            values (ValidationInfo): The validation info containing other field values.

        Returns:
            Optional[str]: The validated AWS region.
        """

        valid_regions = values.data.get("aws_regions", ["us-east-1"])
        if v in [None, ""]:
            return SettingsDefaults.AWS_REGION
        if v not in valid_regions:
            raise AMValueError(f"aws_region {v} not in aws_regions: {valid_regions}")
        return v

    @field_validator("environment")
    def validate_environment(cls, v: Optional[str]) -> str:
        """Validates the `environment` field.

        Args:
            v (Optional[str]): The environment value to validate.

        Returns:
            Optional[str]: The validated environment.
        """
        if v in [None, ""]:
            return SettingsDefaults.ENVIRONMENT
        if not isinstance(v, str):
            raise AMConfigurationError("environment is not a str.")
        return v

    @field_validator("fernet_encryption_key")
    def validate_fernet_encryption_key(cls, v: Optional[str]) -> str:
        """Validates the `fernet_encryption_key` field.

        Args:
            v (Optional[str]): The Fernet encryption key value to validate.

        Raises:
            ValueError: If the Fernet encryption key is invalid.
            AMValueError: If the Fernet encryption key is not found.

        Returns:
            Optional[str]: The validated Fernet encryption key.
        """

        if v in [None, ""]:
            return SettingsDefaults.FERNET_ENCRYPTION_KEY

        if v == DEFAULT_MISSING_VALUE:
            return v

        if not isinstance(v, str):
            raise AMConfigurationError("fernet_encryption_key is not a str.")

        try:
            # Decode the key using URL-safe base64
            decoded_key = base64.urlsafe_b64decode(v)
            # Ensure the decoded key is exactly 32 bytes
            if len(decoded_key) != 32:
                raise ValueError("Fernet key must be exactly 32 bytes when decoded.")
        except (TypeError, ValueError, base64.binascii.Error) as e:  # type: ignore[catch-base-exception]
            raise AMValueError(f"Invalid Fernet encryption key: {v}. Error: {e}") from e

        if not isinstance(v, str):
            raise AMConfigurationError("fernet_encryption_key is not a str.")
        return v

    @field_validator("local_hosts")
    def validate_local_hosts(cls, v: Optional[List[str]]) -> List[str]:
        """Validates the `local_hosts` field.

        Args:
            v (Optional[List[str]]): The local hosts value to validate.

        Returns:
            List[str]: The validated local hosts.
        """
        if v in [None, ""]:
            return SettingsDefaults.LOCAL_HOSTS

        if not isinstance(v, list):
            raise AMConfigurationError("local_hosts is not a list")
        return v

    @field_validator("root_domain")
    def validate_aws_apigateway_root_domain(cls, v: Optional[str]) -> str:
        """
        Validates the `root_domain` field.

        If the value is not set, returns the default root domain.

        Args:
            v (Optional[str]): The root domain value to validate.

        Returns:
            str: The validated root domain.
        """
        if v in [None, ""]:
            return SettingsDefaults.ROOT_DOMAIN

        if not isinstance(v, str):
            raise AMConfigurationError("root_domain is not a str.")

        return v

    @field_validator("aws_eks_cluster_name")
    def validate_aws_eks_cluster_name(cls, v: Optional[str]) -> str:
        """Validates the `aws_eks_cluster_name` field.

        Args:
            v (Optional[str]): The AWS EKS cluster name value to validate.

        Returns:
            str: The validated AWS EKS cluster name.
        """
        if v in [None, ""]:
            return SettingsDefaults.AWS_EKS_CLUSTER_NAME

        if not isinstance(v, str):
            raise AMConfigurationError("aws_eks_cluster_name is not a str.")

        return v

    @field_validator("aws_db_instance_identifier")
    def validate_aws_db_instance_identifier(cls, v: Optional[str]) -> str:
        """Validates the `aws_db_instance_identifier` field.

        Args:
            v (Optional[str]): The AWS RDS DB instance identifier value to validate.

        Returns:
            str: The validated AWS RDS DB instance identifier.
        """
        if v in [None, ""]:
            return SettingsDefaults.AWS_RDS_DB_INSTANCE_IDENTIFIER

        if not isinstance(v, str):
            raise AMConfigurationError("aws_db_instance_identifier is not a str.")

        return v

    @field_validator("debug_mode")
    def parse_debug_mode(cls, v: Optional[Union[bool, str]]) -> bool:
        """Validates the 'debug_mode' field.

        Args:
            v (Union[bool, str]): the debug_mode value to validate

        Returns:
            bool: The validated debug_mode.
        """
        if isinstance(v, bool):
            return v
        if v in [None, ""]:
            return SettingsDefaults.DEBUG_MODE
        if isinstance(v, str):
            return v.lower() in ["true", "1", "t", "y", "yes"]

        raise AMConfigurationError("could not validate debug_mode")

    @field_validator("logo")
    def check_logo(cls, v: Optional[str]) -> str:
        """Validates the `logo` field.

        Args:
            v (str): The logo value to validate.

        Returns:
            str: The validated logo.
        """
        if str(v) in [None, ""] and SettingsDefaults.LOGO is not None:
            return SettingsDefaults.LOGO
        return str(v)

    @field_validator("mailchimp_api_key")
    def check_mailchimp_api_key(cls, v: Optional[SecretStr]) -> SecretStr:
        """Validates the `mailchimp_api_key` field.

        Args:
            v (Optional[SecretStr]): The Mailchimp API key value to validate.

        Returns:
            SecretStr: The validated Mailchimp API key.
        """
        if str(v) in [None, ""] and SettingsDefaults.MAILCHIMP_API_KEY is not None:
            return SettingsDefaults.MAILCHIMP_API_KEY

        if not isinstance(v, SecretStr):
            raise AMConfigurationError("mailchimp_api_key is not a SecretStr")
        return v

    @field_validator("mailchimp_list_id")
    def check_mailchimp_list_id(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `mailchimp_list_id` field.

        Args:
            v (Optional[str]): The Mailchimp list ID value to validate.

        Returns:
            Optional[str]: The validated Mailchimp list ID.
        """
        if str(v) in [None, ""] and SettingsDefaults.MAILCHIMP_LIST_ID is not None:
            return SettingsDefaults.MAILCHIMP_LIST_ID
        return v

    @field_validator("marketing_site_url")
    def check_marketing_site_url(cls, v: Optional[str]) -> str:
        """Validates the `marketing_site_url` field.

        Args:
            v (Optional[str]): The marketing site URL value to validate.
        Returns:
            str: The validated marketing site URL.
        """
        if str(v) in [None, ""] and SettingsDefaults.MARKETING_SITE_URL is not None:
            return SettingsDefaults.MARKETING_SITE_URL
        if not isinstance(v, str):
            raise AMConfigurationError("marketing_site_url is not a str.")
        AMValidator.validate_url(v)
        return v

    @field_validator("stripe_live_secret_key")
    def check_stripe_live_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `stripe_live_secret_key` field.

        Args:
            v (Optional[str]): The Stripe live secret key to validate.

        Returns:
            str: The validated Stripe live secret key.
        """
        if v in [None, ""]:
            warnings.warn(
                "The 'stripe_live_secret_key' field is deprecated and will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            return SettingsDefaults.STRIPE_LIVE_SECRET_KEY

        if not isinstance(v, str):
            raise AMConfigurationError("stripe_live_secret_key is not a str.")
        return v

    @field_validator("stripe_test_secret_key")
    def check_stripe_test_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `stripe_test_secret_key` field.

        Args:
            v (Optional[str]): The Stripe test secret key to validate.
        Returns:
            str: The validated Stripe test secret key.
        """
        if v in [None, ""]:
            warnings.warn(
                "The 'stripe_test_secret_key' field is deprecated and will be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            return SettingsDefaults.STRIPE_TEST_SECRET_KEY

        if not isinstance(v, str):
            raise AMConfigurationError("stripe_test_secret_key is not a str.")
        return v

    @field_validator("secret_key")
    def check_secret_key(cls, v: Optional[str]) -> str:
        """Validates the `secret_key` field.

        Args:
            v (Optional[str]): The secret key value to validate.
        Returns:
            str: The validated secret key.
        """
        if v in [None, ""] and SettingsDefaults.SECRET_KEY is not None:
            return SettingsDefaults.SECRET_KEY

        if not isinstance(v, str):
            raise AMConfigurationError(f"secret_key {type(v)} is not a str.")
        return v

    @field_validator("smtp_sender")
    def check_smtp_sender(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_sender` field.

        Args:
            v (Optional[str]): The SMTP sender email address to validate.

        Returns:
            Optional[str]: The validated SMTP sender email address.
        """
        if v in [None, ""]:
            v = SettingsDefaults.SMTP_SENDER
            AMValidator.validate_domain(v)

        if not isinstance(v, str):
            raise AMConfigurationError("smtp_sender is not a str.")
        return v

    @field_validator("smtp_from_email")
    def check_smtp_from_email(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_from_email` field.

        Args:
            v (Optional[str]): The SMTP from email address to validate.

        Returns:
            Optional[str]: The validated SMTP from email address.
        """
        if v in [None, ""]:
            return SettingsDefaults.SMTP_FROM_EMAIL

        if isinstance(v, str):
            AMValidator.validate_email(v)
            return v

        raise AMConfigurationError("could not validate smtp_from_email.")

    @field_validator("smtp_host")
    def check_smtp_host(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_host` field.

        Args:
            v (Optional[str]): The SMTP host to validate.

        Returns:
            Optional[str]: The validated SMTP host.
        """
        if v in [None, ""]:
            v = SettingsDefaults.SMTP_HOST
            AMValidator.validate_domain(v)

        if not isinstance(v, str):
            raise AMConfigurationError("smtp_host is not a str.")
        return v

    @field_validator("smtp_password")
    def check_smtp_password(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_password` field.

        Args:
            v (Optional[str]): The SMTP password to validate.

        Returns:
            Optional[str]: The validated SMTP password.
        """
        if v in [None, ""]:
            return SettingsDefaults.SMTP_PASSWORD

        if not isinstance(v, str):
            raise AMConfigurationError("smtp_password is not a str.")
        return v

    @field_validator("smtp_port")
    def check_smtp_port(cls, v: Optional[int]) -> Optional[int]:
        """Validates the `smtp_port` field.

        Args:
            v (Optional[int]): The SMTP port to validate.

        Returns:
            int: The validated SMTP port.
        """
        if v in [None, ""]:
            v = SettingsDefaults.SMTP_PORT
        try:
            retval = int(v)  # type: ignore
        except ValueError as e:
            raise AMValueError("Could not convert port number to int.") from e

        if not str(retval).isdigit() or not 1 <= int(retval) <= 65535:
            raise AMValueError("Invalid port number")

        return retval

    @field_validator("smtp_use_ssl")
    def check_smtp_use_ssl(cls, v: Optional[Union[bool, str]]) -> bool:
        """Validates the `smtp_use_ssl` field.

        Args:
            v (Optional[Union[bool, str]]): The SMTP use SSL flag to validate.

        Returns:
            bool: The validated SMTP use SSL flag.
        """
        if isinstance(v, bool):
            return v
        if v in [None, ""]:
            return SettingsDefaults.SMTP_USE_SSL
        return str(v).lower() in ["true", "1", "yes", "on"]

    @field_validator("smtp_use_tls")
    def check_smtp_use_tls(cls, v: Optional[Union[bool, str]]) -> bool:
        """Validates the `smtp_use_tls` field.

        Args:
            v (Optional[Union[bool, str]]): The SMTP use TLS flag to validate.
        Returns:
            bool: The validated SMTP use TLS flag.
        """
        if isinstance(v, bool):
            return v
        if v in [None, ""]:
            return SettingsDefaults.SMTP_USE_TLS
        return str(v).lower() in ["true", "1", "yes", "on"]

    @field_validator("smtp_username")
    def check_smtp_username(cls, v: Optional[str]) -> Optional[str]:
        """Validates the `smtp_username` field.

        Args:
            v (Optional[str]): The SMTP username to validate.

        Returns:
            Optional[str]: The validated SMTP username.
        """
        if v in [None, ""]:
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
