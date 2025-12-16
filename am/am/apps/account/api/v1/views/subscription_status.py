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
from am.apps.account.models import Subscription
from am.apps.account.serializers import SubscriptionSerializer
from am.apps.account.utils import get_cached_subscription
from am.lib.django.request import AMRequestMixin


logger = logging.getLogger(__name__)
REFERRER = "referrer"
REFERRER_HEADER = "X-Client-Domain"


@method_decorator(csrf_exempt, name="dispatch")
class SubscriptionStatusView(APIView):
    r"""
    API view to check the subscription status of a user.
    Clients can provide a 'referrer' in any of the following ways:
    - In the request body (for POST, PUT, PATCH requests) as JSON
    - As a query parameter (for GET requests)
    - In the request headers X-Client-Domain
    - otherwise AMRequestMixin will attempt to determine the domain from the request META.

    Example request:

        curl -X 'GET' http://api.am.localhost:8000/accounts/subscription-status/\?referrer\=platform.smarter.sh

    Supported methods: GET, POST, PUT, PATCH
    200 OK: Subscription found and returned.
    404 Not Found: No active subscription found.
    401 Unauthorized: User is not authenticated.
    403 Forbidden: User does not have permission to access this resource.

    .. note::

        - This view is exempt from CSRF verification to allow access from external clients.
        - Requests from multitenant domains require authentication.
    """

    permission_classes = [AllowAny]

    def get_referrer_from_request(self, request: "AMRequestMixin") -> str | None:
        """
        Extract the referrer from the request in the following order:
        1. From the request data (body)
        2. From the query parameters
        3. From the request headers
        """
        data = request.data
        if isinstance(data, dict) and data.get(REFERRER):
            return str(data.get(REFERRER))

        params = request.params
        if isinstance(params, QueryDict) and params.get(REFERRER):
            return str(params.get(REFERRER))

        meta = request.am_request.META if request.am_request and hasattr(request.am_request, "META") else {}
        header_referrer = meta.get(REFERRER_HEADER)
        if header_referrer:
            return str(header_referrer)

        return None

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                REFERRER_HEADER,
                openapi.IN_HEADER,
                description="Client domain name",
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
        requester_domain = self.get_referrer_from_request(request_mixin)
        if requester_domain:
            request_mixin.requester_domain = requester_domain

        if request_mixin.is_multitenant_domain and not request_mixin.is_authenticated:
            logger.warning(
                "Unauthorized access attempt to multitenant domain: %s from %s",
                request.get_host(),
                request_mixin.requester_domain,
            )
            return Response(status=HTTPStatus.UNAUTHORIZED)

        logger.info("SubscriptionStatusView GET called from: %s", request_mixin.requester_domain)
        plan_type = AMHostingPlanTypeEnum.MULTITENANT if request_mixin.is_multitenant_domain else None
        subscription = get_cached_subscription(
            user=request_mixin.user,
            host=request_mixin.requester_domain,
            account=request_mixin.account,
            plan_type=plan_type,
        )

        retval = {
            "user": request_mixin.user,
            "account": subscription.account if isinstance(subscription, Subscription) else request_mixin.account,
            "subscription": (
                SubscriptionSerializer(subscription).data if isinstance(subscription, Subscription) else None
            ),
        }

        logger.info("No active subscription found for host: %s, %s", request_mixin.domain, retval)
        return Response(data=retval)

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
