"""
The subscription status api, which a multitenant Smarter platform calls when a user signs in.

.. code-block:: bash

    curl https://api.am.example.com/accounts/subscription-status/ \\
      -H 'Authorization: Platform <the platform key>' \\
      -H 'X-Client-Username: <username>' \\
      -H 'X-Client-Email: <email>'

A user may use the platform when they belong (:class:`SubscriptionUser`) to an active, current
MULTITENANT subscription. The platform is identified by its key
(:class:`am.apps.account.models.PlatformClient`), and the user by their username and email
together, so a user of one platform can't be mistaken for another person who has the same
username elsewhere.

Answers:

- 200 with ``active``, ``plan_type`` and ``end_date``: the subscription is active.
- 403: no such user, or no active subscription. The two are answered alike, so the api doesn't
  reveal which usernames exist.
- 400: no username, or, from a platform with a key, no email.
- 401: a wrong platform key, or no key while the ``require_platform_key`` switch is on.

Until that switch is on, a request without a key is still answered, by username alone, so that
platforms keep working while they are given keys.
"""

import logging
from http import HTTPStatus
from typing import Optional

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from am.apps.account.api.v1.authentication import PlatformClientAuthentication
from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.models import PlatformClient, Subscription, User
from am.lib.django.waffle import AMWaffleSwitches, switch_is_active

logger = logging.getLogger(__name__)

USERNAME_HEADER = "X-Client-Username"
EMAIL_HEADER = "X-Client-Email"
DOMAIN_HEADER = "X-Client-Domain"
"""Sent by platforms without a key.

Logged only: a header the caller sets identifies nothing.
"""


def header(request, name: str) -> Optional[str]:
    """
    Return a request header's value, stripped, or None when it is missing or empty.

    :param request: The DRF request.
    :param name: The header's name, e.g. ``X-Client-Username``.
    :returns: The value, or None.
    """
    value = request.headers.get(name)
    if value is None:
        return None
    return value.strip() or None


def get_user(username: str, email: Optional[str]) -> Optional[User]:
    """
    Return the user with this username, and, when given, this email address (in any case).

    :param username: The username.
    :param email: The email address, or None to match by username alone.
    :returns: The user, or None.
    """
    users = User.objects.filter(username=username, is_active=True)
    if email is not None:
        users = users.filter(email__iexact=email)
    return users.first()


def get_active_multitenant_subscription(user: User) -> Optional[Subscription]:
    """
    Return an active, current MULTITENANT subscription that the user belongs to.

    :param user: The user.
    :returns: The subscription that ends last, or None.
    """
    today = timezone.now().date()
    return (
        Subscription.objects.filter(
            subscription_users__user=user,
            plan_type=AMHostingPlanTypeEnum.MULTITENANT.value,
            active=True,
            start_date__lte=today,
            end_date__gt=today,
        )
        .order_by("-end_date")
        .first()
    )


@method_decorator(csrf_exempt, name="dispatch")
class SubscriptionStatusView(APIView):
    """
    Answer whether a user may use the multitenant Smarter platform that asks.

    GET is the method. POST, PUT and PATCH are accepted and answered alike, for older callers.
    """

    authentication_classes = [PlatformClientAuthentication]
    # who may ask is decided in get(): a platform key, or no key until the switch requires one.
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "Authorization",
                openapi.IN_HEADER,
                description="Platform <key>",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                USERNAME_HEADER, openapi.IN_HEADER, description="The user's username", type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                EMAIL_HEADER,
                openapi.IN_HEADER,
                description="The user's email address. Required with a platform key.",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: "active", 400: "bad request", 401: "unauthorized", 403: "no active subscription"},
    )
    def get(self, request, *args, **kwargs):
        """
        Answer whether the user in the request's headers has an active multitenant subscription.

        :param request: The DRF request.
        :returns: 200 with the subscription's status, or 400, 401 or 403 (see the module).
        """
        client = request.auth if isinstance(request.auth, PlatformClient) else None
        if client is None and switch_is_active(AMWaffleSwitches.REQUIRE_PLATFORM_KEY):
            return Response(status=HTTPStatus.UNAUTHORIZED, headers={"WWW-Authenticate": "Platform"})

        username = header(request, USERNAME_HEADER)
        email = header(request, EMAIL_HEADER)
        if username is None or (client is not None and email is None):
            return Response(status=HTTPStatus.BAD_REQUEST)
        platform = client.host_name if client is not None else f"{header(request, DOMAIN_HEADER)} (no platform key)"

        user = get_user(username, email if client is not None else None)
        subscription = get_active_multitenant_subscription(user) if user is not None else None
        if subscription is None:
            logger.info("SubscriptionStatusView.get() no active subscription for a user of %s", platform)
            return Response(status=HTTPStatus.FORBIDDEN)

        logger.info("SubscriptionStatusView.get() active subscription %s for a user of %s", subscription.pk, platform)
        return Response(
            {
                "active": True,
                "plan_type": AMHostingPlanTypeEnum(subscription.plan_type).name.lower(),
                "end_date": subscription.end_date.isoformat(),
            }
        )

    def post(self, request, *args, **kwargs):
        """Answer as GET does."""
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """Answer as GET does."""
        return self.get(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        """Answer as GET does."""
        return self.get(request, *args, **kwargs)
