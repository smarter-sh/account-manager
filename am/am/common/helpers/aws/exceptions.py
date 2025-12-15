"""Custom exceptions for the AWS module."""

from am.common.exceptions import AMException


class AMAWSError(AMException):
    """Base class for AWS errors."""


class AWSNotReadyError(AMAWSError):
    """Raised when the AWS client is not ready."""


class AWSACMVerificationFailed(AMAWSError):
    """Raised when the verification of an ACM certificate fails."""


class AWSACMVerificationTimeout(AMAWSError):
    """Raised when the verification of an ACM certificate times out."""


class AWSRoute53RecordVerificationTimeout(AMAWSError):
    """Raised when the verification of a Route53 record times out."""


class AWSACMVerificationNotFound(AMAWSError):
    """Raised when the verification of an ACM certificate is not found."""


class AWSACMCertificateNotFound(AMAWSError):
    """Raised when an ACM certificate is not found."""


class AWSRoute53RecordNotFound(AMAWSError):
    """Raised when a Route53 record is not found."""


class AWSRoute53ZoneNotFound(AMAWSError):
    """Raised when a Route53 zone is not found."""


class AWSRoute53HostedZoneAlreadyExists(AMAWSError):
    """Raised when a Route53 zone already exists."""
