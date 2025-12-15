"""Account Manager API enumerations."""

ROOT_DOMAIN = "smarter.sh"
VERSION_PREFIX = f"am.{ROOT_DOMAIN}"


class AMApiVersions:
    """API Version enumeration."""

    V1 = f"{VERSION_PREFIX}/v1"

    @classmethod
    def all_values(cls):
        return [value for name, value in vars(AMApiVersions).items() if not name.startswith("__")]
