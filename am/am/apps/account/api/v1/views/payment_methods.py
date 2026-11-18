# pylint: disable=W0707,W0718
"""Account payment method views for Account Manager API."""

import logging
from http import HTTPStatus

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from am.apps.account.models import PaymentMethod
from am.apps.account.serializers import PaymentMethodSerializer
from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper

from .base import AccountListViewBase, AccountViewBase


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.ACCOUNT_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


class PaymentMethodView(AccountViewBase):
    """
    Payment method view for Account Manager API.

    A superuser may read and delete any PaymentMethod. A staff user may do so only
    for the PaymentMethods of their own Account.
    """

    serializer_class = PaymentMethodSerializer

    def get_payment_method(self, payment_method_id: int) -> PaymentMethod:
        """
        The PaymentMethod that the request user asked for, if they may see it.

        :param payment_method_id: The PaymentMethod's id.
        :returns: The PaymentMethod.
        :raises Http404: when it does not exist, or is not in the request user's Account.
        """
        if self.is_request_superuser:
            return get_object_or_404(PaymentMethod, pk=payment_method_id)
        return get_object_or_404(PaymentMethod, pk=payment_method_id, account=self.get_request_user_account())

    def get(self, request: Request, payment_method_id: int):
        """
        Return a PaymentMethod as json.

        :param request: The request.
        :param payment_method_id: The PaymentMethod's id.
        :returns: The serialized PaymentMethod.
        """
        logger.info("%s.get() payment_method_id: %s", self.formatted_class_name, payment_method_id)
        payment_method = self.get_payment_method(payment_method_id)
        return Response(PaymentMethodSerializer(payment_method).data, status=HTTPStatus.OK)

    def delete(self, request: Request, payment_method_id: int):
        """
        Delete a PaymentMethod.

        :param request: The request.
        :param payment_method_id: The PaymentMethod's id.
        :returns: An empty 204 response.
        """
        logger.info("%s.delete() payment_method_id: %s", self.formatted_class_name, payment_method_id)
        self.get_payment_method(payment_method_id).delete()
        return Response(status=HTTPStatus.NO_CONTENT)


class PaymentMethodsListView(AccountListViewBase):
    """Payment methods list view for Account Manager API."""

    serializer_class = PaymentMethodSerializer

    def get_queryset(self) -> QuerySet[PaymentMethod]:
        """
        The PaymentMethods the request user may see.

        :returns: Every PaymentMethod for a superuser, else those of the request user's Accounts.
        """
        if self.is_request_superuser:
            return PaymentMethod.objects.all().order_by("pk")
        return PaymentMethod.objects.filter(account__users__user=self.request_user).order_by("pk")
