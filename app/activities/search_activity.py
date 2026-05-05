# app/activities/search_activity.py
from temporalio import activity
from duckduckgo_search import DDGS
from app.models import SearchResult


@activity.defn
async def search_activity(query: str) -> SearchResult:
    activity.logger.info(f"Searching: {query}")

    # DuckDuckGo is synchronous — run in executor to not block the event loop
    import asyncio
    loop = asyncio.get_event_loop()

    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=5))

    raw_results = await loop.run_in_executor(None, _search)

    snippets = [r.get("body", "") for r in raw_results if r.get("body")]
    sources = [r.get("href", "") for r in raw_results if r.get("href")]

    return SearchResult(
        query=query,
        snippets=snippets[:5],
        sources=sources[:5],
    )