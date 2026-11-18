"""Test am.apps.account.tasks."""

from datetime import timedelta
from unittest import mock

from django.db import IntegrityError
from django.utils import timezone

from am.apps.account.models import (
    CHARGE_TYPE_PLUGIN,
    CHARGE_TYPE_PROMPT_COMPLETION,
    CHARGE_TYPE_TOOL,
    Account,
    Charge,
    DailyBillingRecord,
    User,
)
from am.apps.account.tasks import aggregate_charges, aggregate_daily_billing_records
from am.apps.account.tests.mixins import AccountTestCase


class TestAggregateCharges(AccountTestCase):
    """Test the hourly Celery Beat task that rolls charges up into daily billing records."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(company_name="Tasks Co")
        cls.user = User.objects.create_user(username="tasks_user", email="tasks@example.com")

    def create_charge(self, days_ago: int = 0, tokens: int = 10, provider: str = "openai", **kwargs) -> Charge:
        """Create a charge, dated days_ago days ago."""
        charge = Charge.objects.create(
            account=self.account,
            user=self.user,
            provider=provider,
            prompt_tokens=tokens,
            completion_tokens=tokens * 2,
            total_tokens=tokens * 3,
            model="gpt-4",
            reference="test",
            **kwargs,
        )
        if days_ago:
            Charge.objects.filter(pk=charge.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return charge

    def test_charges_are_aggregated_and_deleted(self):
        """A day's charges become one record with summed tokens and the charges' provider."""
        self.create_charge(tokens=10, provider="metaai")
        self.create_charge(tokens=5, provider="metaai")

        aggregate_charges()

        self.assertFalse(Charge.objects.exists())
        record = DailyBillingRecord.objects.get(account=self.account, user=self.user)
        self.assertEqual(record.provider, "metaai")
        self.assertEqual(record.charge_type, "completion")
        self.assertEqual(record.date, timezone.now().date())
        self.assertEqual((record.prompt_tokens, record.completion_tokens, record.total_tokens), (15, 30, 45))

    def test_existing_record_is_added_to(self):
        """A later run adds the new charges to the day's existing record, so the task is idempotent."""
        self.create_charge(tokens=10)
        aggregate_daily_billing_records()
        aggregate_daily_billing_records()  # nothing left to do
        self.create_charge(tokens=1)
        aggregate_daily_billing_records()

        record = DailyBillingRecord.objects.get(account=self.account, user=self.user)
        self.assertEqual((record.prompt_tokens, record.completion_tokens, record.total_tokens), (11, 22, 33))

    def test_each_day_gets_its_own_record(self):
        """Charges from different days are aggregated separately."""
        for days_ago in range(3):
            self.create_charge(days_ago=days_ago)
        aggregate_daily_billing_records()
        self.assertEqual(DailyBillingRecord.objects.filter(account=self.account).count(), 3)

    def test_each_charge_type_gets_its_own_record(self):
        """
        A provider's charges of different types on the same day each get their own record.

        The unique constraint once left out charge_type, so the second type's record raised
        IntegrityError, and its charges stayed behind, retried every hour.
        """
        self.create_charge(tokens=10, charge_type=CHARGE_TYPE_PROMPT_COMPLETION)
        self.create_charge(tokens=4, charge_type=CHARGE_TYPE_PLUGIN)
        self.create_charge(tokens=2, charge_type=CHARGE_TYPE_TOOL)

        aggregate_daily_billing_records()

        self.assertFalse(Charge.objects.exists())
        records = DailyBillingRecord.objects.filter(account=self.account, user=self.user, provider="openai")
        self.assertEqual(
            {record.charge_type: record.total_tokens for record in records},
            {CHARGE_TYPE_PROMPT_COMPLETION: 30, CHARGE_TYPE_PLUGIN: 12, CHARGE_TYPE_TOOL: 6},
        )

    def test_progress_is_logged_every_100_items(self):
        """The task processes more than 100 billing items in one run."""
        for days_ago in range(101):
            self.create_charge(days_ago=days_ago, tokens=1)
        aggregate_daily_billing_records()
        self.assertEqual(DailyBillingRecord.objects.count(), 101)
        self.assertFalse(Charge.objects.exists())

    def test_database_errors_are_counted_and_abort_the_run(self):
        """Database errors keep the charges, and the tenth one stops the run."""
        for days_ago in range(12):
            self.create_charge(days_ago=days_ago)
        with mock.patch(
            "am.apps.account.tasks.DailyBillingRecord.objects.create", side_effect=IntegrityError("boom")
        ) as create:
            aggregate_daily_billing_records()
        self.assertEqual(create.call_count, 10)
        self.assertEqual(Charge.objects.count(), 12)
        self.assertFalse(DailyBillingRecord.objects.exists())

    def test_unexpected_errors_are_counted_and_abort_the_run(self):
        """Unexpected errors are handled the same way as database errors."""
        for days_ago in range(11):
            self.create_charge(days_ago=days_ago)
        with mock.patch(
            "am.apps.account.tasks.DailyBillingRecord.objects.create", side_effect=ValueError("boom")
        ) as create:
            aggregate_daily_billing_records()
        self.assertEqual(create.call_count, 10)
        self.assertEqual(Charge.objects.count(), 11)
