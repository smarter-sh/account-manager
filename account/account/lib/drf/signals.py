"""Signals for the Account Manager API."""

from django.dispatch import Signal


smarter_token_authentication_request = Signal()
smarter_token_authentication_success = Signal()
smarter_token_authentication_failure = Signal()
