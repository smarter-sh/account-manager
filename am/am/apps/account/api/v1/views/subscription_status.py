# pylint: disable=W0613
"""
API Views for checking subscription status.
"""
from http import HTTPStatus

from rest_framework.response import Response
from rest_framework.views import APIView

from am.apps.account.enum import AMHostingPlanTypeEnum
from am.apps.account.models import Subscription
from am.apps.account.serializers import SubscriptionSerializer
from am.apps.account.utils import get_cached_subscription
from am.lib.django.request import AMRequestMixin


class SubscriptionStatusView(APIView):
    """
    API view to check the subscription status of a user.
    """

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to retrieve subscription status.
        """
        request_mixin = AMRequestMixin(request=request)

        subscription = get_cached_subscription(
            user=request_mixin.user,
            host=request_mixin.domain,
            account=request_mixin.account,
            plan_type=AMHostingPlanTypeEnum.MULTITENANT if request_mixin.is_multitenant_domain else None,
        )
        if isinstance(subscription, Subscription):
            return Response(SubscriptionSerializer(subscription).data)

        return Response({"detail": "No active subscription found."}, status=HTTPStatus.NOT_FOUND)

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
