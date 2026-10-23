from __future__ import annotations

from typing import Any, Callable

from app.config import (
    APIFY_API_TOKEN,
    APIFY_GOOGLE_ACTOR,
    APIFY_YANDEX_ACTOR,
    APIFY_YANDEX_MAPS_ACTOR,
)
from app.models import SearchResultItem
from app.scraper.search_utils import build_search_phrase


def apify_enabled() -> bool:
    return bool(APIFY_API_TOKEN)


def _client():
    if not APIFY_API_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN не задан в .env")
    from apify_client import ApifyClient

    return ApifyClient(APIFY_API_TOKEN)


def _run_actor(actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    client = _client()
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        return []
    return list(client.dataset(dataset_id).iterate_items())


def _pick_url(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pick_text(item: dict[str, Any], *keys: str) -> str | None:
    value = _pick_url(item, *keys)
    return value or None


def _map_items(
    raw_items: list[dict[str, Any]],
    *,
    normalize_url: Callable[[str], str | None],
    title_keys: tuple[str, ...],
    url_keys: tuple[str, ...],
    snippet_keys: tuple[str, ...],
    position_keys: tuple[str, ...] = ("position", "rank", "order"),
    page_keys: tuple[str, ...] = ("page", "pageNumber"),
    require_website: bool = False,
) -> list[SearchResultItem]:
    results: list[SearchResultItem] = []
    seen_urls: set[str] = set()

    for item in raw_items:
        url = None
        for key in url_keys:
            candidate = item.get(key)
            if isinstance(candidate, str):
                url = normalize_url(candidate)
                if url:
                    break
        if not url or url in seen_urls:
            continue
        if require_website and not url.startswith("http"):
            continue

        title = _pick_text(item, *title_keys) or url
        snippet = _pick_text(item, *snippet_keys)

        position = len(results) + 1
        for key in position_keys:
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                position = value
                break

        page_number = 1
        for key in page_keys:
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                page_number = value
                break

        seen_urls.add(url)
        results.append(
            SearchResultItem(
                position=position,
                title=title,
                url=url,
                snippet=snippet,
                page=page_number,
            )
        )

    return results


def _flatten_organic(items: list[dict[str, Any]], *container_keys: str) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in items:
        expanded = False
        for key in container_keys:
            nested = item.get(key)
            if isinstance(nested, list) and nested:
                flattened.extend(nested)
                expanded = True
                break
        if not expanded:
            flattened.append(item)
    return flattened


def apify_google_serp(query: str, city: str, max_pages: int) -> tuple[str, list[SearchResultItem]]:
    from app.scraper.google import normalize_url as normalize_google_url

    search_phrase = build_search_phrase(query, city)
    items = _run_actor(
        APIFY_GOOGLE_ACTOR,
        {
            "queries": search_phrase,
            "maxPagesPerQuery": max_pages,
            "resultsPerPage": 10,
            "countryCode": "ru",
            "languageCode": "ru",
        },
    )
    organic = _flatten_organic(items, "organicResults", "results", "items")
    results = _map_items(
        organic,
        normalize_url=normalize_google_url,
        title_keys=("title", "name"),
        url_keys=("url", "link", "href"),
        snippet_keys=("description", "snippet", "text"),
    )
    if not results:
        raise RuntimeError("Apify Google actor вернул пустой результат")
    return search_phrase, results


def apify_yandex_serp(query: str, city: str, max_pages: int) -> tuple[str, list[SearchResultItem]]:
    from app.scraper.yandex import normalize_url as normalize_yandex_url

    search_phrase = build_search_phrase(query, city)
    items = _run_actor(
        APIFY_YANDEX_ACTOR,
        {
            "text": search_phrase,
            "yandex_domain": "yandex.ru",
            "lang": "ru",
            "max_pages": max_pages,
            "groups_on_page": 10,
        },
    )
    # Один элемент датасета на страницу выдачи: ссылки в organic_results, номер страницы в page_number.
    organic: list[dict[str, Any]] = []
    for item in items:
        page_number = item.get("page_number")
        for row in item.get("organic_results") or []:
            if isinstance(row, dict):
                organic.append({**row, "page": page_number})
    results = _map_items(
        organic,
        normalize_url=normalize_yandex_url,
        title_keys=("title", "name"),
        url_keys=("url", "link", "href"),
        snippet_keys=("snippet", "description", "text"),
        # Сквозная нумерация по всем страницам, как в Playwright-парсере.
        position_keys=(),
    )
    if not results:
        raise RuntimeError("Apify Yandex actor вернул пустой результат")
    return search_phrase, results


def apify_yandex_maps(query: str, city: str, max_pages: int) -> tuple[str, list[SearchResultItem]]:
    from app.scraper.yandex_maps import normalize_url as normalize_maps_url

    search_phrase = build_search_phrase(query, city)
    max_results = max(10, max_pages * 15)
    items = _run_actor(
        APIFY_YANDEX_MAPS_ACTOR,
        {
            "query": [query],
            "location": city,
            "maxResults": max_results,
            "language": "ru",
        },
    )

    results: list[SearchResultItem] = []
    seen_urls: set[str] = set()
    for item in items:
        url = _pick_url(item, "website", "url", "site", "websiteUrl")
        normalized = normalize_maps_url(url) if url else None
        if not normalized or normalized in seen_urls:
            continue

        title = _pick_text(item, "title", "name", "businessName") or normalized
        address = _pick_text(item, "address", "fullAddress", "formattedAddress")
        phones = item.get("phones") or item.get("phone")
        phone_text = None
        if isinstance(phones, list) and phones:
            phone_text = str(phones[0])
        elif isinstance(phones, str):
            phone_text = phones

        snippet_parts = [part for part in (address, phone_text) if part]
        snippet = " | ".join(snippet_parts) if snippet_parts else None

        seen_urls.add(normalized)
        results.append(
            SearchResultItem(
                position=len(results) + 1,
                title=title,
                url=normalized,
                snippet=snippet,
                page=1,
            )
        )

    if not results:
        raise RuntimeError("Apify Yandex Maps actor вернул пустой результат")
    return search_phrase, results
