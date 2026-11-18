"""Test the AMTestBase class."""

import os

from django.http import HttpRequest

from am.lib.unittest.base_classes import AMTestBase

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


class TestAMTestBase(AMTestBase):
    """Test the AMTestBase helpers."""

    def test_class_attributes(self):
        self.assertEqual(len(self.hash_suffix), 16)
        self.assertIn(self.hash_suffix, self.name)
        self.assertEqual(len(self.uid), 64)

    def test_generate_hash_suffix(self):
        self.assertEqual(len(AMTestBase.generate_hash_suffix(8)), 8)
        self.assertNotEqual(AMTestBase.generate_hash_suffix(), AMTestBase.generate_hash_suffix())

    def test_readers(self):
        expected = {"name": "example", "items": [1, 2]}
        self.assertEqual(self.get_readonly_yaml_file(os.path.join(DATA, "example.yaml")), expected)
        self.assertEqual(self.get_readonly_json_file(os.path.join(DATA, "example.json")), expected)
        self.assertEqual(
            self.get_readonly_csv_file(os.path.join(DATA, "example.csv")),
            [{"name": "alice", "email": "alice@example.com"}, {"name": "bob", "email": "bob@example.com"}],
        )

    def test_create_generic_request(self):
        request = self.create_generic_request(url="http://example.com/api/v1/")
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/api/v1/")
        self.assertEqual(request.content_type, "application/json")
