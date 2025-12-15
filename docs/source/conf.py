# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import subprocess
import sys


HERE = os.path.abspath(os.path.dirname(__file__))
AM_ROOT = os.path.abspath(os.path.join(HERE, "../../am/"))
sys.path.insert(0, AM_ROOT)

from am.__version__ import __version__  # noqa: F401
from am.common.conf import account_settings


if not account_settings.environment:
    raise RuntimeError("The 'account_settings.environment' variable is not set.")

os.environ["DJANGO_SETTINGS_MODULE"] = "am.settings." + account_settings.environment

import django


django.setup()

project = "Account Manager"

# pylint: disable=redefined-builtin
copyright = f"{datetime.datetime.now().year}"
author = "Lawrence McDaniel"
release = __version__

try:
    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
# pylint: disable=broad-except
except Exception:
    commit = None

from datetime import datetime


last_updated = datetime.now().strftime("%Y-%m-%d")

html_context = {
    "commit": commit,
    "last_updated": last_updated,
}

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Account Manager"
copyright = "2025, Lawrence P. McDaniel"
author = "Lawrence P. McDaniel"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib_django",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
    "sphinx_design",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinxcontrib.autodoc_pydantic",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = []
django_settings = "smarter.settings.prod"
todo_include_todos = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": ("https://docs.djangoproject.com/en/5.2/", "https://docs.djangoproject.com/en/5.2/_objects/"),
}
rst_epilog = f"""
.. |project_version| replace:: {release}
"""


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
}
html_static_path = ["_static"]
html_css_files = [
    "custom.css",
]
