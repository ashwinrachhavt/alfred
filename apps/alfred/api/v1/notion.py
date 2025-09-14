from alfred.core.config import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/v1/notion", tags=["notion"])


@router.get("/status")
def status():
    configured = bool(settings.notion_token)
    details = {
        "NOTION_TOKEN": configured,
        "NOTION_PARENT_PAGE_ID": bool(settings.notion_parent_page_id),
        "NOTION_CLIENTS_DB_ID": bool(settings.notion_clients_db_id),
        "NOTION_NOTES_DB_ID": bool(settings.notion_notes_db_id),
    }
    return {"configured": configured, "details": details}


@router.get("/search")
def notion_search(query: str = "", page_size: int = 25):
    from alfred.services import notion as svc
    return svc.search(query=query, page_size=page_size)


@router.get("/page/{page_id}")
def page(page_id: str):
    from alfred.services import notion as svc
    return svc.get_page(page_id)


@router.get("/page/{page_id}/children")
def page_children(page_id: str, page_size: int = 50):
    from alfred.services import notion as svc
    return svc.list_block_children(page_id, page_size=page_size)


@router.get("/database/{db_id}/query")
def db_query(db_id: str, page_size: int = 50):
    from alfred.services import notion as svc
    return svc.query_database(db_id, page_size=page_size)


@router.get("/clients")
def clients():
    from alfred.services import notion as svc
    return svc.list_clients()


@router.get("/notes")
def notes():
    from alfred.services import notion as svc
    return svc.list_notes()


@router.post("/pages")
def create_page(title: str, md: str):
    from alfred.services import notion as svc
    return svc.create_simple_page(title, md)


@router.get("/page/{page_id}/markdown", response_class=PlainTextResponse)
def page_markdown(page_id: str):
    """Render a Notion page's content as Markdown text."""
    from alfred.services import notion as svc
    try:
        md = svc.page_to_markdown(page_id)
    except HTTPException:
        raise
    except Exception as e:
        # Provide a concise error back to caller
        raise HTTPException(500, f"Failed to render markdown: {e}")
    return md
