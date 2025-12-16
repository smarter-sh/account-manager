"""
This module defines the complete set of host patterns for Account Manager,
organized by logical group.

API Subdomain Hosts
-------------------
.. list-table:: API Subdomain Hosts
   :header-rows: 1

   * - Host
     - Description
   * - api.localhost:8000
     - Local API endpoint for http://api.localhost:8000/
   * - api.127.0.0.1:8000
     - Local API endpoint for http://api.127.0.0.1:8000/
   * - api.example.com
     - Main production API endpoint.
   * - alpha.api.example.com
     - Alpha environment for the API.
   * - beta.api.example.com
     - Beta environment for the API.
   * - next.api.example.com
     - Next environment for the API.

"""

from django_hosts import host, patterns

from am.common.conf import am_settings
from am.common.const import AMEnvironments
from am.urls import api as api_urls
from am.urls import console as console_urls


host_patterns = patterns(
    "",
    # -------------------------------------------------------------------------
    # Admin console
    # -------------------------------------------------------------------------
    host(r"localhost:8000", console_urls, name="localhost"),  # for http://localhost:8000/
    host(r"127.0.0.1:8000", console_urls, name="127001"),  # for http://127.0.0.1:8000/
    host(
        rf"{am_settings.am_subdomain}.{am_settings.root_domain}",
        console_urls,
        name=am_settings.am_subdomain,
    ),  # for https://platform.example.com/
    host(
        rf"{AMEnvironments.ALPHA}.{am_settings.am_subdomain}.{am_settings.root_domain}",
        console_urls,
        name=f"{AMEnvironments.ALPHA}_{am_settings.am_subdomain}",
    ),  # for https://alpha.platform.example.com/
    host(
        rf"{AMEnvironments.BETA}.{am_settings.am_subdomain}.{am_settings.root_domain}",
        console_urls,
        name=f"{AMEnvironments.BETA}_{am_settings.am_subdomain}",
    ),  # for https://beta.platform.example.com/
    host(
        rf"{AMEnvironments.NEXT}.{am_settings.am_subdomain}.{am_settings.root_domain}",
        console_urls,
        name=f"{AMEnvironments.NEXT}_{am_settings.am_subdomain}",
    ),  # for https://next.platform.example.com/
    # -------------------------------------------------------------------------
    # API subdomains
    # -------------------------------------------------------------------------
    host(r"api.localhost:8000", api_urls, name="api_localhost"),  # for http://api.localhost:8000/
    host(r"api.127.0.0.1:8000", api_urls, name="api_127001"),  # for http://api.127.0.0.1:8000/
    host(
        rf"{am_settings.api_subdomain}.{am_settings.root_domain}",
        api_urls,
        name=am_settings.api_subdomain,
    ),  # for https://api.platform.example.com/
    host(
        rf"{AMEnvironments.ALPHA}.{am_settings.api_subdomain}.{am_settings.root_domain}",
        api_urls,
        name=f"{AMEnvironments.ALPHA}_{am_settings.api_subdomain}",
    ),  # for https://alpha.api.platform.example.com/
    host(
        rf"{AMEnvironments.BETA}.{am_settings.api_subdomain}.{am_settings.root_domain}",
        api_urls,
        name=f"{AMEnvironments.BETA}_{am_settings.api_subdomain}",
    ),  # for https://beta.api.platform.example.com/
    host(
        rf"{AMEnvironments.NEXT}.{am_settings.api_subdomain}.{am_settings.root_domain}",
        api_urls,
        name=f"{AMEnvironments.NEXT}_{am_settings.api_subdomain}",
    ),  # for https://next.api.platform.example.com/
)

__all__ = ["host_patterns"]
