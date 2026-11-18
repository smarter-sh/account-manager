"""Test the configuration Settings class in am.common.conf."""

import logging
import os
import tempfile
import warnings
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
from pydantic import SecretStr, ValidationError

from am.common import conf
from am.common.conf import (
    DEFAULT_AWS_REGIONS,
    DEFAULT_MISSING_VALUE,
    Settings,
    SettingsDefaults,
    bool_environment_variable,
    get_aws_regions,
    get_settings,
)
from am.common.const import (
    ACCOUNT_API_KEY_MAX_LIFETIME_DAYS,
    AMEnvironments,
    load_tfvars,
)
from am.common.exceptions import AMConfigurationError, AMValueError
from am.lib.unittest.base_classes import AMTestBase

SMTP_VALUES = {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_username": "user",
    "smtp_password": "password",
    "smtp_from_email": "no-reply@example.com",
}


def make_settings(**kwargs) -> Settings:
    """Build a Settings object from constructor values alone, ignoring the container's environment."""
    with patch.dict(os.environ, {}, clear=True):
        return Settings(**kwargs)


def make_settings_from_env(env: dict, **kwargs) -> Settings:
    """Build a Settings object whose only environment variables are ``env``."""
    with patch.dict(os.environ, env, clear=True):
        return Settings(**kwargs)


# pylint: disable=too-many-public-methods
class TestConfiguration(AMTestBase):
    """Test am.common.conf."""

    # -------------------------------------------------------------------------
    # module functions
    # -------------------------------------------------------------------------
    def test_bool_environment_variable(self):
        """Unset variables return the default; set ones are parsed as booleans."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(bool_environment_variable("AM_TEST_BOOL", True))
            self.assertFalse(bool_environment_variable("AM_TEST_BOOL", False))
        for value in ["true", "True", "1", "t", "Y", "yes"]:
            with patch.dict(os.environ, {"AM_TEST_BOOL": value}, clear=True):
                self.assertTrue(bool_environment_variable("AM_TEST_BOOL", False), value)
        for value in ["false", "False", "0", "no", ""]:
            with patch.dict(os.environ, {"AM_TEST_BOOL": value}, clear=True):
                self.assertFalse(bool_environment_variable("AM_TEST_BOOL", True), value)

    @patch("am.common.conf.boto3.Session")
    def test_get_aws_regions_without_credentials(self, mock_session):
        """Without AWS credentials, EC2 is not asked and the default regions are returned."""
        mock_session.return_value.get_credentials.return_value = None
        self.assertEqual(get_aws_regions("us-east-1"), DEFAULT_AWS_REGIONS)
        mock_session.return_value.client.assert_not_called()

    @patch("am.common.conf.boto3.Session")
    def test_get_aws_regions_with_credentials(self, mock_session):
        """With AWS credentials, the regions come from EC2."""
        session = mock_session.return_value
        session.get_credentials.return_value = MagicMock()
        session.client.return_value.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "eu-west-1"}]
        }
        self.assertEqual(get_aws_regions("us-east-2"), ["us-east-1", "eu-west-1"])
        mock_session.assert_called_once_with(region_name="us-east-2")
        session.client.assert_called_once_with("ec2")

    @patch("am.common.conf.boto3.Session")
    def test_get_aws_regions_errors(self, mock_session):
        """Boto3 and AWS errors fall back to the default regions."""
        errors = [
            ProfileNotFound(profile="missing"),
            NoCredentialsError(),
            ClientError({"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}}, "DescribeRegions"),
        ]
        for error in errors:
            mock_session.reset_mock()
            mock_session.side_effect = error
            self.assertEqual(get_aws_regions(), DEFAULT_AWS_REGIONS)

        mock_session.side_effect = None
        mock_session.return_value.get_credentials.return_value = MagicMock()
        mock_session.return_value.client.return_value.describe_regions.side_effect = errors[2]
        self.assertEqual(get_aws_regions(), DEFAULT_AWS_REGIONS)

    def test_default_regions_accept_any_real_region(self):
        """
        Without AWS, e.g. with an unknown AWS_PROFILE, aws_region may still be any real region.

        The fallback was once ["us-east-1"] alone, so a CI run whose .env had
        AWS_REGION=us-east-2 and AWS_PROFILE=SET-ME-PLEASE failed at startup.
        """
        for region in ("us-east-1", "us-east-2", "us-west-2", "eu-west-1", "ap-southeast-2"):
            with self.subTest(region=region):
                settings = make_settings(aws_regions=DEFAULT_AWS_REGIONS, aws_region=region)
                self.assertEqual(settings.aws_region, region)
        with self.assertRaises(AMValueError):
            make_settings(aws_regions=DEFAULT_AWS_REGIONS, aws_region="us-east-9")

    def test_database_settings_come_from_am_mysql_variables(self):
        """
        The database is set by AM_MYSQL_* alone; an unprefixed MYSQL_HOST, e.g. left in an old .env, is ignored.

        pydantic-settings would otherwise read the field mysql_host from MYSQL_HOST.
        """
        env = {"AM_MYSQL_HOST": "smarter-mariadb.example.svc.cluster.local", "MYSQL_HOST": "old.example.com"}
        settings = make_settings_from_env(env)
        self.assertEqual(settings.mysql_host, "smarter-mariadb.example.svc.cluster.local")
        self.assertEqual(make_settings_from_env({"MYSQL_HOST": "old.example.com"}).mysql_host, "am-mariadb")
        settings = make_settings(AM_MYSQL_HOST="db.example.com", AM_MYSQL_PORT=3307)
        self.assertEqual((settings.mysql_host, settings.mysql_port), ("db.example.com", 3307))

    def test_get_settings_wraps_validation_errors(self):
        """Get_settings() raises AMConfigurationError when the settings don't validate."""
        try:
            make_settings(debug_mode="not-a-bool")
        except ValidationError as e:
            validation_error = e
        else:
            self.fail("debug_mode='not-a-bool' should not validate")

        get_settings.cache_clear()
        try:
            with patch("am.common.conf.Settings", side_effect=validation_error):
                with self.assertRaises(AMConfigurationError):
                    get_settings()
        finally:
            get_settings.cache_clear()

    def test_get_settings_is_a_singleton(self):
        """Get_settings() returns the same object every time."""
        self.assertIs(get_settings(), get_settings())
        self.assertIsInstance(conf.am_settings, Settings)

    def test_load_tfvars(self):
        """Load_tfvars() reads a terraform.tfvars file, and returns {} if there is none."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "terraform.tfvars")
            self.assertEqual(load_tfvars(path), {})
            with open(path, "w", encoding="utf-8") as f:
                f.write('root_domain = "example.com"\ndebug_mode = true\n')
            tfvars = load_tfvars(path)
        self.assertEqual(tfvars["root_domain"], "example.com")
        self.assertTrue(tfvars["debug_mode"])

    # -------------------------------------------------------------------------
    # fields
    # -------------------------------------------------------------------------
    def test_defaults(self):
        """With no environment and no constructor values, settings equal SettingsDefaults."""
        settings = make_settings()
        self.assertEqual(settings.aws_region, SettingsDefaults.AWS_REGION)
        self.assertEqual(settings.debug_mode, SettingsDefaults.DEBUG_MODE)
        self.assertEqual(settings.developer_mode, SettingsDefaults.DEVELOPER_MODE)
        self.assertEqual(settings.environment, SettingsDefaults.ENVIRONMENT)
        self.assertEqual(settings.root_domain, SettingsDefaults.ROOT_DOMAIN)
        self.assertEqual(settings.local_hosts, SettingsDefaults.LOCAL_HOSTS)
        self.assertEqual(settings.log_level, SettingsDefaults.LOG_LEVEL)
        self.assertEqual(settings.secret_key, SettingsDefaults.SECRET_KEY)
        self.assertEqual(settings.smtp_port, SettingsDefaults.SMTP_PORT)
        self.assertEqual(settings.smtp_use_tls, SettingsDefaults.SMTP_USE_TLS)
        self.assertEqual(settings.default_missing_value, DEFAULT_MISSING_VALUE)
        self.assertEqual(
            settings.aws_access_key_id.get_secret_value(), SettingsDefaults.AWS_ACCESS_KEY_ID.get_secret_value()
        )

    def test_local_hosts_default(self):
        """The local hosts include localhost, 127.0.0.1 and the test client's host."""
        self.assertIn("localhost:8000", SettingsDefaults.LOCAL_HOSTS)
        self.assertIn("127.0.0.1:8000", SettingsDefaults.LOCAL_HOSTS)
        self.assertIn("testserver", SettingsDefaults.LOCAL_HOSTS)

    def test_log_level_follows_debug_mode(self):
        """LOG_LEVEL is DEBUG only when DEBUG_MODE is true."""
        expected = logging.DEBUG if SettingsDefaults.DEBUG_MODE else logging.INFO
        self.assertEqual(SettingsDefaults.LOG_LEVEL, expected)
        self.assertIsInstance(SettingsDefaults.DEBUG_MODE, bool)
        self.assertIsInstance(SettingsDefaults.SMTP_USE_TLS, bool)

    def test_environment_variables_override_defaults(self):
        """Settings reads its fields from environment variables."""
        settings = make_settings_from_env(
            {
                "DEBUG_MODE": "True",
                "DEVELOPER_MODE": "false",
                "ENVIRONMENT": "alpha",
                "ROOT_DOMAIN": "example.org",
                "SMTP_PORT": "465",
                "SMTP_USE_SSL": "yes",
                "SMTP_USE_TLS": "no",
            }
        )
        self.assertTrue(settings.debug_mode)
        self.assertFalse(settings.developer_mode)
        self.assertEqual(settings.environment, "alpha")
        self.assertEqual(settings.root_domain, "example.org")
        self.assertEqual(settings.smtp_port, 465)
        self.assertTrue(settings.smtp_use_ssl)
        self.assertFalse(settings.smtp_use_tls)

    def test_constructor_values(self):
        """Constructor values take precedence over the environment."""
        settings = make_settings_from_env(
            {"ENVIRONMENT": "beta"},
            environment="prod",
            debug_mode=True,
            aws_regions=["us-east-1", "eu-west-1"],
            aws_region="eu-west-1",
            root_domain="example.net",
        )
        self.assertEqual(settings.environment, "prod")
        self.assertTrue(settings.debug_mode)
        self.assertEqual(settings.aws_region, "eu-west-1")
        self.assertEqual(settings.root_domain, "example.net")

    def test_invalid_debug_mode(self):
        """A value that is not a boolean does not validate."""
        with self.assertRaises(ValidationError):
            make_settings_from_env({"DEBUG_MODE": "maybe"})

    def test_settings_are_immutable(self):
        """Settings can't be changed after they are created."""
        settings = make_settings()
        with self.assertRaises(ValidationError):
            settings.aws_region = "us-west-2"
        with self.assertRaises(ValidationError):
            settings.debug_mode = not settings.debug_mode

    def test_aws_region(self):
        """Aws_region must be one of aws_regions; an empty one is the default."""
        settings = make_settings(aws_regions=["us-east-1", "us-west-2"], aws_region="us-west-2")
        self.assertEqual(settings.aws_region, "us-west-2")
        self.assertEqual(make_settings(aws_region="").aws_region, SettingsDefaults.AWS_REGION)
        with self.assertRaises(AMValueError):
            make_settings(aws_regions=["us-east-1"], aws_region="eu-west-1")

    def test_aws_profile(self):
        """An empty aws_profile is the default one."""
        self.assertEqual(make_settings(aws_profile="").aws_profile, SettingsDefaults.AWS_PROFILE)
        self.assertEqual(make_settings(aws_profile="am-test").aws_profile, "am-test")

    def test_aws_keys(self):
        """AWS keys are kept, unless they are empty or a non-default aws_profile is set."""
        settings = make_settings(
            aws_profile=SettingsDefaults.AWS_PROFILE,
            aws_access_key_id="AKIAEXAMPLEEXAMPLE00",
            aws_secret_access_key="example-secret",
        )
        self.assertIsInstance(settings.aws_access_key_id, SecretStr)
        self.assertEqual(settings.aws_access_key_id.get_secret_value(), "AKIAEXAMPLEEXAMPLE00")
        self.assertEqual(settings.aws_secret_access_key.get_secret_value(), "example-secret")
        self.assertNotIn("example-secret", str(settings.aws_secret_access_key))

        settings = make_settings(aws_access_key_id="", aws_secret_access_key="")
        self.assertEqual(settings.aws_access_key_id, SettingsDefaults.AWS_ACCESS_KEY_ID)
        self.assertEqual(settings.aws_secret_access_key, SettingsDefaults.AWS_SECRET_ACCESS_KEY)

        settings = make_settings(
            aws_profile="am-test-profile",
            aws_access_key_id="AKIAEXAMPLEEXAMPLE00",
            aws_secret_access_key="example-secret",
        )
        self.assertEqual(settings.aws_access_key_id, SettingsDefaults.AWS_ACCESS_KEY_ID)
        self.assertEqual(settings.aws_secret_access_key, SettingsDefaults.AWS_SECRET_ACCESS_KEY)

    def test_empty_strings_are_defaults(self):
        """Empty string values are replaced by their defaults."""
        settings = make_settings(
            environment="",
            root_domain="",
            secret_key="",
            smtp_sender="",
            smtp_from_email="",
            smtp_host="",
            smtp_password="",
            smtp_username="",
        )
        self.assertEqual(settings.environment, SettingsDefaults.ENVIRONMENT)
        self.assertEqual(settings.root_domain, SettingsDefaults.ROOT_DOMAIN)
        self.assertEqual(settings.secret_key, SettingsDefaults.SECRET_KEY)
        self.assertEqual(settings.smtp_sender, SettingsDefaults.SMTP_SENDER)
        self.assertEqual(settings.smtp_from_email, SettingsDefaults.SMTP_FROM_EMAIL)
        self.assertEqual(settings.smtp_host, SettingsDefaults.SMTP_HOST)
        self.assertEqual(settings.smtp_password, SettingsDefaults.SMTP_PASSWORD)
        self.assertEqual(settings.smtp_username, SettingsDefaults.SMTP_USERNAME)

    def test_none_values_are_defaults(self):
        """None is replaced by the default for the optional fields."""
        settings = make_settings(
            secret_key=None,
            smtp_sender=None,
            smtp_from_email=None,
            smtp_host=None,
            smtp_password=None,
            smtp_username=None,
            smtp_port=None,
            smtp_use_ssl=None,
            smtp_use_tls=None,
        )
        self.assertEqual(settings.secret_key, SettingsDefaults.SECRET_KEY)
        self.assertEqual(settings.smtp_port, SettingsDefaults.SMTP_PORT)
        self.assertEqual(settings.smtp_use_ssl, SettingsDefaults.SMTP_USE_SSL)
        self.assertEqual(settings.smtp_use_tls, SettingsDefaults.SMTP_USE_TLS)
        self.assertEqual(settings.smtp_host, SettingsDefaults.SMTP_HOST)

    def test_explicit_values_are_kept(self):
        """Non-empty values pass validation unchanged."""
        settings = make_settings(
            secret_key="example-secret-key",
            smtp_sender="example.com",
            smtp_from_email="sender@example.com",
            smtp_host="smtp.example.com",
            smtp_password="password",
            smtp_username="user",
            smtp_use_ssl=True,
            smtp_use_tls=False,
        )
        self.assertEqual(settings.secret_key, "example-secret-key")
        self.assertEqual(settings.smtp_sender, "example.com")
        self.assertEqual(settings.smtp_from_email, "sender@example.com")
        self.assertEqual(settings.smtp_host, "smtp.example.com")
        self.assertEqual(settings.smtp_password, "password")
        self.assertEqual(settings.smtp_username, "user")
        self.assertTrue(settings.smtp_use_ssl)
        self.assertFalse(settings.smtp_use_tls)

    def test_smtp_from_email_must_be_an_email_address(self):
        """An invalid smtp_from_email is refused."""
        with self.assertRaises(AMValueError):
            make_settings(smtp_from_email="not-an-email")

    def test_smtp_port_range(self):
        """Smtp_port must be between 1 and 65535."""
        self.assertEqual(make_settings(smtp_port=1).smtp_port, 1)
        self.assertEqual(make_settings(smtp_port=65535).smtp_port, 65535)
        for port in [0, -1, 65536]:
            with self.assertRaises(AMValueError):
                make_settings(smtp_port=port)
        with self.assertRaises(ValidationError):
            make_settings_from_env({"SMTP_PORT": "not-a-port"})

    def test_stripe_keys(self):
        """Empty Stripe keys are the defaults, with a deprecation warning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = make_settings(stripe_live_secret_key="", stripe_test_secret_key=None)
        self.assertEqual(settings.stripe_live_secret_key, SettingsDefaults.STRIPE_LIVE_SECRET_KEY)
        self.assertEqual(settings.stripe_test_secret_key, SettingsDefaults.STRIPE_TEST_SECRET_KEY)
        self.assertEqual(len([w for w in caught if issubclass(w.category, DeprecationWarning)]), 2)

        settings = make_settings(stripe_live_secret_key="sk_live_example", stripe_test_secret_key="sk_test_example")
        self.assertEqual(settings.stripe_live_secret_key, "sk_live_example")
        self.assertEqual(settings.stripe_test_secret_key, "sk_test_example")

    # -------------------------------------------------------------------------
    # properties
    # -------------------------------------------------------------------------
    def test_smtp_is_configured(self):
        """Smtp_is_configured is True only when every required SMTP value is set."""
        self.assertTrue(make_settings(**SMTP_VALUES).smtp_is_configured)
        for field in ["smtp_username", "smtp_password"]:
            values = {**SMTP_VALUES, field: DEFAULT_MISSING_VALUE}
            self.assertFalse(make_settings(**values).smtp_is_configured, field)

    def test_local_environment_properties(self):
        """Domains and urls of a local environment."""
        settings = make_settings(environment=AMEnvironments.LOCAL, root_domain="example.com")
        self.assertTrue(settings.environment_is_local)
        self.assertEqual(settings.am_subdomain, "am")
        self.assertEqual(settings.api_subdomain, "api")
        self.assertEqual(settings.am_domain, "am.example.com")
        self.assertEqual(settings.am_api_domain, "api.am.example.com")
        self.assertEqual(settings.platform_subdomain, "platform")
        self.assertEqual(settings.platform_domain, "platform.example.com")
        self.assertEqual(settings.environment_domain, "am.localhost:8000")
        self.assertEqual(settings.environment_api_domain, "api.am.localhost:8000")
        self.assertEqual(settings.environment_cdn_domain, "cdn.alpha.am.example.com")
        self.assertEqual(settings.environment_url, "http://am.localhost:8000/")
        self.assertEqual(settings.environment_api_url, "http://api.am.localhost:8000/")
        self.assertEqual(settings.aws_s3_bucket_name, "alpha.am.example.com")

    def test_alpha_environment_properties(self):
        """Domains and urls of a non-production AWS environment."""
        settings = make_settings(environment=AMEnvironments.ALPHA, root_domain="example.com")
        self.assertFalse(settings.environment_is_local)
        self.assertEqual(settings.environment_domain, "alpha.am.example.com")
        self.assertEqual(settings.environment_api_domain, "alpha.api.am.example.com")
        self.assertEqual(settings.environment_cdn_domain, "cdn.alpha.am.example.com")
        self.assertEqual(settings.environment_url, "https://alpha.am.example.com/")
        self.assertEqual(settings.environment_api_url, "https://alpha.api.am.example.com/")
        self.assertEqual(settings.aws_s3_bucket_name, "alpha.am.example.com")

    def test_prod_environment_properties(self):
        """Domains and urls of the production environment."""
        settings = make_settings(environment=AMEnvironments.PROD, root_domain="example.com")
        self.assertEqual(settings.environment_domain, "am.example.com")
        self.assertEqual(settings.environment_api_domain, "api.am.example.com")
        self.assertEqual(settings.environment_cdn_domain, "cdn.am.example.com")
        self.assertEqual(settings.environment_url, "https://am.example.com/")
        self.assertEqual(settings.environment_api_url, "https://api.am.example.com/")
        self.assertEqual(settings.aws_s3_bucket_name, "am.example.com")

    def test_smarter_api_key_max_lifetime_days(self):
        """The api key lifetime is the constant from am.common.const."""
        self.assertEqual(make_settings().smarter_api_key_max_lifetime_days, ACCOUNT_API_KEY_MAX_LIFETIME_DAYS)
