# pylint: disable=W0613
"""
API Views for checking subscription status.
"""
import logging
from http import HTTPStatus

from django.http import QueryDict
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.serializers import SubscriptionSerializer
from am.apps.account.utils import get_cached_subscription, get_cached_user_for_username
from am.lib.django.request import AMRequestMixin


logger = logging.getLogger(__name__)
REQUESTER = "requester"
REQUESTER_HEADER = "X-Client-Domain"
USERNAME = "username"
USERNAME_HEADER = "X-Client-Username"


@method_decorator(csrf_exempt, name="dispatch")
class SubscriptionStatusView(APIView):
    r"""
    API view to check the subscription status of a user.
    Clients can provide a 'requester' in any of the following ways:
    - In the request body (for POST, PUT, PATCH requests) as JSON
    - As a query parameter (for GET requests)
    - In the request headers X-Client-Domain
    - otherwise AMRequestMixin will attempt to determine the domain from the request META.

    Example request:

        curl -X 'GET' http://api.am.localhost:8000/accounts/subscription-status/\?requester\=platform.smarter.sh

    Supported methods: GET, POST, PUT, PATCH
    200 OK: Subscription found and returned.
    403 Forbidden: User does not have an active subscription.
    404 Not Found: User not found.

    .. note::

        - This view is exempt from CSRF verification to allow access from external clients.
    """

    permission_classes = [AllowAny]

    def get_from_request_body(self, request: "AMRequestMixin", key: str) -> str | None:
        """
        Extract a value from the request body.
        """
        data = request.data
        if isinstance(data, dict) and data.get(key):
            logger.info("Found %s in request body: %s", key, data.get(key))
            return str(data.get(key))
        return None

    def get_from_request_params(self, request: "AMRequestMixin", key: str) -> str | None:
        """
        Extract a value from the request query parameters.
        """
        params = request.params
        if isinstance(params, QueryDict) and params.get(key):
            logger.info("Found %s in request params: %s", key, params.get(key))
            return str(params.get(key))
        return None

    def get_from_request_headers(self, request: "AMRequestMixin", key: str) -> str | None:
        """
        Extract a value from the request headers. The header keys arrive differently in Django's META.
        example: 'X-Client-Domain' becomes 'HTTP_X_CLIENT_DOMAIN'
        """
        key = f"HTTP_{key.upper().replace('-', '_')}"
        meta = request.am_request.META if request.am_request and hasattr(request.am_request, "META") else {}
        header_value = meta.get(key)
        if header_value:
            logger.info("Found %s in request headers: %s", key, header_value)
            return str(header_value)
        return None

    def get_from_request(self, request: "AMRequestMixin", key: str) -> str | None:
        """
        Extract a value from the request in the following order:
        1. Request body
        2. Query parameters
        3. Request headers
        """
        logger.info("Attempting to retrieve %s from request", key)
        return self.get_from_request_body(request, key) or self.get_from_request_params(request, key)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                REQUESTER_HEADER,
                openapi.IN_HEADER,
                description=f"Client {REQUESTER} domain",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                USERNAME_HEADER,
                openapi.IN_HEADER,
                description=f"Client {USERNAME}",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to retrieve subscription status.
        """
        request_mixin = AMRequestMixin(request=request)
        requester_domain = (
            self.get_from_request(request_mixin, REQUESTER)
            or self.get_from_request_headers(request_mixin, REQUESTER_HEADER)
            or request_mixin.requester_domain
        )

        requester_username = self.get_from_request(request_mixin, USERNAME) or self.get_from_request_headers(
            request_mixin, USERNAME_HEADER
        )
        logger.info("SubscriptionStatusView GET called from: %s for user: %s", requester_domain, requester_username)
        user = get_cached_user_for_username(requester_username) if requester_username else None
        if not user:
            logger.warning(
                "User not found for domain: %s, username: %s",
                requester_domain,
                requester_username,
            )
            return Response(status=HTTPStatus.NOT_FOUND)

        if requester_domain:
            request_mixin.requester_domain = requester_domain

        plan_type = AMHostingPlanTypeEnum.MULTITENANT if request_mixin.is_multitenant_domain else None
        subscription = get_cached_subscription(
            user=user,
            host=request_mixin.requester_domain,
            account=request_mixin.account,
            plan_type=plan_type,
        )
        if not subscription:
            logger.warning(
                "No active subscription found for user: %s on host: %s",
                requester_username,
                request_mixin.requester_domain,
            )
            return Response(status=HTTPStatus.FORBIDDEN)

        data = SubscriptionSerializer(subscription).data
        return Response(data)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests to retrieve subscription status.
        """
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        Handle PUT requests to retrieve subscription status.
        """
        return self.get(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH requests to retrieve subscription status.
        """
        return self.get(request, *args, **kwargs)
