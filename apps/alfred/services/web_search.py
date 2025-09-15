from alfred.connectors.web_connector import WebConnector


def search_web(
    q: str,
    mode: str = "auto",
    *,
    brave_pages: int = 10,
    ddg_max_results: int = 50,
    exa_num_results: int = 100,
    tavily_max_results: int = 20,
    tavily_topic: str = "general",
    you_num_results: int = 20,
) -> dict:
    conn = WebConnector(
        mode=mode,
        brave_pages=brave_pages,
        ddg_max_results=ddg_max_results,
        exa_num_results=exa_num_results,
        tavily_max_results=tavily_max_results,
        tavily_topic=tavily_topic,
        you_num_results=you_num_results,
    )
    resp = conn.search(q)
    return {
        "provider": resp.provider,
        "query": resp.query,
        "meta": resp.meta,
        "hits": [
            {"title": h.title, "url": h.url, "snippet": h.snippet, "source": h.source}
            for h in resp.hits
        ],
    }
