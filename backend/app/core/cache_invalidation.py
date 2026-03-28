"""Cache invalidation helpers for read-heavy dashboard endpoints."""

from typing import Literal

from .cache import get_response_cache
from .logger import logger


_SUMMARY_EXACT_KEYS = (
    "analytics:dashboard-summary:v1",
    "analytics:overview:v1",
    "analytics:categories:v1",
    "analytics:status-distribution:v1",
    "analytics:years-in-business:v1",
)

_SUMMARY_PREFIX_KEYS = (
    "analytics:locations:v1",
)

_TREND_PREFIX_KEYS = (
    "analytics:monthly-trends:v1",
    "analytics:weekly-trends:v1",
)


async def _invalidate_summary_cache() -> int:
    cache = get_response_cache()
    removed_total = 0

    for key in _SUMMARY_EXACT_KEYS:
        if await cache.delete(key):
            removed_total += 1

    for prefix in _SUMMARY_PREFIX_KEYS:
        removed_total += await cache.delete_prefix(prefix)

    return removed_total


async def _invalidate_trend_cache() -> int:
    cache = get_response_cache()
    removed_total = 0

    for prefix in _TREND_PREFIX_KEYS:
        removed_total += await cache.delete_prefix(prefix)

    return removed_total


async def invalidate_analytics_cache(
    scope: Literal["all", "summary", "summary_and_trends", "trends"] = "all",
) -> int:
    """Invalidate analytics response-cache entries by scope.

    Scopes:
    - all: Remove every analytics cache key.
    - summary: Remove dashboard/overview/distribution caches.
    - trends: Remove monthly/weekly trend caches.
    - summary_and_trends: Remove summary and trend caches.
    """
    cache = get_response_cache()

    if scope == "all":
        removed_total = await cache.delete_prefix("analytics:")
    elif scope == "summary":
        removed_total = await _invalidate_summary_cache()
    elif scope == "trends":
        removed_total = await _invalidate_trend_cache()
    else:
        removed_total = await _invalidate_summary_cache()
        removed_total += await _invalidate_trend_cache()

    if removed_total:
        logger.info("Invalidated %d analytics cache entries (scope=%s)", removed_total, scope)

    return removed_total
