"""Test the cache module: the cache_results decorator and lazy_cache."""

import threading
from unittest.mock import MagicMock, patch

from django.core.cache import cache as django_cache
from django.test import SimpleTestCase

from am.lib.unittest.base_classes import AMTestBase

from ..cache import (
    CACHE_MISS_SENTINEL,
    CACHE_NONE_SENTINEL,
    CacheSentinel,
    LazyCache,
    cache_results,
    database_name,
    lazy_cache,
)


class TestCacheResults(AMTestBase):
    """Test the cache_results decorator, against the real (redis) cache."""

    def setUp(self):
        super().setUp()
        self.calls = MagicMock()
        # a per-test argument keeps the cache keys of concurrent test runs apart
        self.arg = self.generate_hash_suffix()

    def decorate(self, return_value, **decorator_kwargs):
        """Return a decorated function that counts its calls and returns return_value."""

        @cache_results(timeout=60, **decorator_kwargs)
        def expensive(x, y=None):
            self.calls(x, y)
            return return_value

        self.addCleanup(expensive.invalidate, self.arg)
        return expensive

    def test_miss_then_hit(self):
        func = self.decorate("computed")
        self.assertEqual(func(self.arg), "computed")
        self.assertEqual(func(self.arg), "computed")
        self.calls.assert_called_once_with(self.arg, None)

    def test_none_is_cached(self):
        func = self.decorate(None)
        self.assertIsNone(func(self.arg))
        self.assertIsNone(func(self.arg))
        self.calls.assert_called_once()

    def test_different_arguments_are_cached_separately(self):
        func = self.decorate("computed")
        func(self.arg)
        func(self.arg, y=1)
        self.addCleanup(func.invalidate, self.arg, y=1)
        self.assertEqual(self.calls.call_count, 2)

    def test_invalidate(self):
        func = self.decorate("computed")
        func(self.arg)
        func.invalidate(self.arg)
        func(self.arg)
        self.assertEqual(self.calls.call_count, 2)

    def test_unpicklable_arguments_are_not_cached(self):
        func = self.decorate("computed")
        lock = threading.Lock()
        self.assertEqual(func(lock), "computed")
        self.assertEqual(func(lock), "computed")
        self.assertEqual(self.calls.call_count, 2)
        self.assertIsNone(func.invalidate(lock))

    @patch("am.lib.cache.logger")
    def test_logging_when_switch_is_on(self, mock_logger):
        func = self.decorate("computed")
        with patch.object(LazyCache, "cache_logging", new=True):
            func(self.arg)
            func(self.arg)
            func.invalidate(self.arg)
        messages = [c.args[0] for c in mock_logger.info.call_args_list if "cache" in c.args[0]]
        self.assertEqual(len([m for m in messages if "cache miss" in m]), 1)
        self.assertEqual(len([m for m in messages if "cache hit" in m]), 1)
        self.assertEqual(len([m for m in messages if "invalidated" in m]), 1)

    @patch("am.lib.cache.logger")
    def test_no_logging_when_disabled(self, mock_logger):
        func = self.decorate("computed", logging_enabled=False)
        with patch.object(LazyCache, "cache_logging", new=True):
            func(self.arg)
            func(self.arg)
        mock_logger.info.assert_not_called()


class TestLazyCache(SimpleTestCase):
    """Test the LazyCache wrapper."""

    def test_delegates_to_django_cache(self):
        key = "am.lib.tests.test_cache.TestLazyCache"
        self.addCleanup(django_cache.delete, key)
        lazy_cache.set(key, 1, timeout=60)
        self.assertEqual(django_cache.get(key), 1)
        self.assertEqual(lazy_cache.get(key), 1)
        self.assertEqual(lazy_cache.incr(key), 2)
        self.assertTrue(lazy_cache.delete(key))
        self.assertEqual(lazy_cache.get(key, "default"), "default")

    def test_first_access_runs_diagnostics(self):
        cache = LazyCache()
        with patch("am.lib.cache.logger") as mock_logger:
            self.assertIs(cache.cache, django_cache)
            self.assertIs(cache.cache, django_cache)
        mock_logger.error.assert_not_called()
        mock_logger.warning.assert_not_called()

    def test_diagnostics_report_a_broken_cache(self):
        cache = LazyCache()
        with (
            patch("django.core.cache.cache") as mock_cache,
            patch("django.core.cache.caches", {"default": object()}),
            patch("am.lib.cache.logger") as mock_logger,
        ):
            mock_cache.get.return_value = None
            cache.cache  # pylint: disable=pointless-statement
            mock_cache.set.side_effect = ConnectionError("down")
            LazyCache().cache  # pylint: disable=pointless-statement
        errors = [c.args[0] for c in mock_logger.error.call_args_list]
        self.assertIn("Django cache is not working as expected.", errors)
        self.assertIn("Error accessing Django cache: %s", errors)
        mock_logger.warning.assert_called()

    def test_cache_logging_reads_the_waffle_switch(self):
        cache = LazyCache()
        with patch("am.lib.django.waffle.switch_is_active", return_value=True) as mock_switch:
            self.assertTrue(cache.cache_logging)
        mock_switch.assert_called_once()


class TestCacheSentinel(SimpleTestCase):
    """Test the CacheSentinel class."""

    def test_str_and_repr(self):
        self.assertEqual(str(CACHE_MISS_SENTINEL), "CACHE_MISS")
        self.assertRegex(repr(CACHE_MISS_SENTINEL), r"^<CacheSentinel: [0-9a-f]{32}>$")
        self.assertEqual(repr(CacheSentinel("CACHE_MISS")), repr(CACHE_MISS_SENTINEL))
        self.assertIsInstance(CACHE_NONE_SENTINEL, str)


class TestDatabaseName(SimpleTestCase):
    """Test that cache keys are scoped to the database."""

    def test_database_name(self):
        from django.db import connections  # pylint: disable=import-outside-toplevel

        self.assertEqual(database_name(), connections["default"].settings_dict["NAME"])

    def test_keys_differ_by_database(self):
        calls = MagicMock(return_value="computed")

        @cache_results(timeout=60)
        def scoped(x):
            return calls(x)

        arg = AMTestBase.generate_hash_suffix()
        for name in ("db_one", "db_two"):
            with patch("am.lib.cache.database_name", return_value=name):
                scoped(arg)
                scoped(arg)
                scoped.invalidate(arg)
        self.assertEqual(calls.call_count, 2)
