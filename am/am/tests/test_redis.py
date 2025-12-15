# pylint: disable=wrong-import-position
"""Test User."""

from django.core.cache import caches

from am.lib.unittest.base_classes import AMTestBase


class TestRedis(AMTestBase):
    """Test Account model"""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.cache = caches["default"]

    def tearDown(self):
        """Clean up test fixtures."""
        self.cache.clear()
        super().tearDown()

    def test_redis_is_available(self):
        """Test that Redis cache is reachable."""
        self.cache.set("test_key", "test_value")
        result = self.cache.get("test_key")
        self.assertEqual(result, "test_value")
