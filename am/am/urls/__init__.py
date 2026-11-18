"""
URLs for the Account Manager: console.py for the web console (ROOT_URLCONF),.

and api.py for the api host (see am.hosts).

The submodules are not imported here: am.apps.api.v1.views.openapi imports
am.urls.api, and am.urls.console imports openapi, so importing console from
this package would make a circular import.
"""
