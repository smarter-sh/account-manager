"""
Update Account Manager's semantic version in every file that holds it.

Called by semantic-release (see release.config.js, @semantic-release/exec), with
the version of the release it is about to cut, before @semantic-release/git
commits these files.

Usage::

    python3 scripts/bump_version.py <new_version>

Updates:

- am/am/__version__.py
- pyproject.toml
- Dockerfile
- helm/charts/account-manager/Chart.yaml (appVersion)
- helm/charts/account-manager/values.yaml (global.image.tag, as v<version>)
"""

import re
import sys
from pathlib import Path

# semantic version: ##.##.## or ##.##.##-label.n, as semantic-release cuts on alpha and beta
SEMANTIC_VERSION_REGEX = r"^\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?$"

# (file, pattern, replacement template). Each pattern must match exactly once.
VERSION_LOCATIONS = (
    ("am/am/__version__.py", r'^__version__\s*=\s*["\'][^"\']*["\']', '__version__ = "{version}"'),
    ("pyproject.toml", r'^version\s*=\s*["\'][^"\']*["\']', 'version = "{version}"'),
    ("Dockerfile", r'org\.opencontainers\.image\.version="[^"]*"', 'org.opencontainers.image.version="{version}"'),
    ("helm/charts/account-manager/Chart.yaml", r"^appVersion:\s*\S+", "appVersion: {version}"),
    # the image tag of global.image, the only tag in the chart's values
    ("helm/charts/account-manager/values.yaml", r"^(\s+tag:\s*)v\d+\.\d+\.\d+\S*", "\\g<1>v{version}"),
)


def update_version_in_file(filepath: str, pattern: str, replacement: str) -> None:
    """
    Replace the one match of ``pattern`` in a file with ``replacement``.

    :param filepath: The file, relative to the repository's root.
    :param pattern: A regular expression, matched per line (``re.MULTILINE``).
    :param replacement: The text that replaces the match.
    :raises ValueError: If the pattern matches no line, or more than one.
    """
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"{filepath}: expected one version to replace, found {count}")
    path.write_text(new_text, encoding="utf-8")
    print(f"Updated {filepath}")


def main() -> None:
    """Validate the version given on the command line, and write it to every file."""
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/bump_version.py <new_version>")
        sys.exit(1)
    new_version = sys.argv[1].removeprefix("v")
    if not re.match(SEMANTIC_VERSION_REGEX, new_version):
        print("Error: Version must be in format ##.##.## or ##.##.##-label.n (e.g., 0.1.20 or 0.2.0-alpha.1)")
        sys.exit(1)

    for filepath, pattern, template in VERSION_LOCATIONS:
        update_version_in_file(filepath, pattern, template.format(version=new_version))


if __name__ == "__main__":
    main()
