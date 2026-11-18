# pylint: disable=W0613
"""Django Authentication views."""

import logging
from typing import Optional

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    HttpResponseServerError,
)
from django.urls import reverse

from am.apps.account.models import User, get_resolved_user
from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.view_helpers import AMNeverCachedWebView, redirect_and_expire_cache
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return (
        waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING)
        and waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING)
        and level >= am_settings.log_level
    )


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class LoginView(AMNeverCachedWebView):
    """
    View for logging in a browser session.

    ``GET`` sends an anonymous user to the Django admin's sign-in page, which is the
    console's sign-in form (``settings.LOGIN_URL`` points here), keeping the query
    string so that ``?next=`` still works. ``POST`` signs a user in with an email
    address and password.
    """

    class LoginForm(forms.Form):
        """Form for the sign-in page."""

        email = forms.EmailField()
        password = forms.CharField(widget=forms.PasswordInput)

    def get(self, request, *args, **kwargs) -> HttpResponseRedirect:
        """
        Redirect to ``/`` when the user is signed in, else to the admin sign-in page.

        :param request: The request.
        :returns: The redirect.
        """
        logger.info("%s.get() called", self.formatted_class_name)
        user = get_resolved_user(request.user) if getattr(request, "user", None) is not None else None
        if user is not None and user.is_authenticated:
            return redirect_and_expire_cache(path="/")
        path = reverse("admin:login")
        query_string = request.META.get("QUERY_STRING")
        if query_string:
            path = f"{path}?{query_string}"
        return redirect_and_expire_cache(path=path)

    def post(
        self, request, *args, **kwargs
    ) -> HttpResponseRedirect | HttpResponseBadRequest | HttpResponseForbidden | HttpResponseServerError:
        """
        Sign a user in with the email address and password of the posted form.

        :param request: The request.
        :returns: A redirect to ``/`` on success, else a plain-text 400, 403 or 500 response.
            (The ``AMHttpResponse*`` classes render ``400.html`` and friends, which this
            repository does not have.)
        """
        form = LoginView.LoginForm(request.POST)
        authenticated_user: Optional[User] = None
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = User.objects.get(email=email)
                password = form.cleaned_data["password"]
                authenticated_user = authenticate(request, username=user.username, password=password)  # type: ignore[assignment]
                if authenticated_user is not None:
                    login(request, authenticated_user)
                    return redirect_and_expire_cache(path="/")
                return HttpResponseBadRequest("Username and/or password do not match.")
            except User.DoesNotExist:
                return HttpResponseForbidden("Invalid login attempt. Unknown user.")
            # pylint: disable=W0718
            except Exception as e:
                logger.error("%s.post() unexpected error: %s", self.formatted_class_name, type(e).__name__)
                return HttpResponseServerError("An unknown error occurred.")
        return HttpResponseBadRequest("Received invalid responses.")


class LogoutView(AMNeverCachedWebView):
    """View for logging out browser session."""

    def get(self, request, *args, **kwargs) -> HttpResponseRedirect:
        """
        Sign the user out and redirect to ``/``.

        :param request: The request.
        :returns: The redirect.
        """
        logout(request)
        return redirect_and_expire_cache(path="/")

    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        """
        Sign the user out and redirect to ``/``.

        :param request: The request.
        :returns: The redirect.
        """
        logout(request)
        return redirect_and_expire_cache(path="/")
