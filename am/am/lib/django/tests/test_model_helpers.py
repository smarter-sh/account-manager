"""Test the TimestampedModel base class, through AMAuthToken, a concrete subclass."""

from unittest.mock import patch

from django.core.exceptions import ValidationError

from am.apps.account.tests.mixins import TestAccountMixin
from am.lib.django.model_helpers import TimestampedModel
from am.lib.drf.models import AMAuthToken


class TestTimestampedModel(TestAccountMixin):
    """Test the TimestampedModel class."""

    def setUp(self):
        super().setUp()
        self.record, _ = AMAuthToken.objects.create(user=self.admin_user, name=self.name)
        self.addCleanup(self.record.delete)

    def test_timestamps_are_set(self):
        self.assertIsNotNone(self.record.created_at)
        self.assertIsNotNone(self.record.updated_at)
        updated_at = self.record.updated_at
        self.record.description = "changed"
        self.record.save()
        self.assertGreaterEqual(self.record.updated_at, updated_at)

    def test_validation_error_aborts_save(self):
        with patch.object(AMAuthToken, "validate", side_effect=ValidationError("bad value")):
            with self.assertRaises(ValidationError) as ctx:
                self.record.save()
        message = str(ctx.exception)
        self.assertIn("bad value", message)
        self.assertIn("model=AMAuthToken", message)
        self.assertNotIn(self.record.digest, message)

    def test_str(self):
        self.assertEqual(TimestampedModel.__str__(self.record), f"AMAuthToken(pk={self.record.pk})")
