"""Test the am.lib.json module."""

import datetime
import decimal
import uuid

from django.test import SimpleTestCase
from django.utils.translation import gettext_lazy

from am.lib import json


class Unserializable:
    """An object that the json module can't serialize."""

    def __str__(self):
        return "unserializable"


class TestJson(SimpleTestCase):
    """Test the json module."""

    def test_dumps_indents_by_two(self):
        self.assertEqual(json.dumps({"a": 1}), '{\n  "a": 1\n}')

    def test_dumps_django_types(self):
        value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        data = json.loads(
            json.dumps(
                {
                    "datetime": datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
                    "date": datetime.date(2024, 1, 2),
                    "decimal": decimal.Decimal("1.50"),
                    "uuid": value,
                    "lazy": gettext_lazy("Hello"),
                }
            )
        )
        self.assertEqual(
            data,
            {
                "datetime": "2024-01-02T03:04:05Z",
                "date": "2024-01-02",
                "decimal": "1.50",
                "uuid": str(value),
                "lazy": "Hello",
            },
        )

    def test_dumps_falls_back_to_str(self):
        self.assertEqual(json.loads(json.dumps({"x": Unserializable()})), {"x": "unserializable"})

    def test_dumps_explicit_default(self):
        self.assertEqual(json.loads(json.dumps({"x": Unserializable()}, default=lambda o: "custom")), {"x": "custom"})

    def test_reexports(self):
        self.assertEqual(json.loads("[1]"), [1])
        with self.assertRaises(json.JSONDecodeError):
            json.loads("{")
