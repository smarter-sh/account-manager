"""Signals for api app."""

from django.dispatch import Signal

api_request_initiated = Signal()
"""
Sent when an API request is initiated.

:Arguments::

    - sender: The sender of the signal.
    - instance: The instance making the request.
    - request: The HTTP request object.

:Example::

    .. code-block:: python

        api_request_initiated.send(sender=self.__class__, instance=self, request=self.request)
"""

api_request_completed = Signal()
"""
Sent when an API request is completed.

:Arguments::
    - sender: The sender of the signal.
    - instance: The instance making the request.
    - request: The HTTP request object.
    - response: The HTTP response object.

:Example::

    .. code-block:: python

        api_request_completed.send(sender=self.__class__, instance=self, request=request, response=response)
"""
