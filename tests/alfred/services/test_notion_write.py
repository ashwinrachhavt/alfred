import pytest

from alfred.services import notion


class DummyBlocksChildren:
    def __init__(self):
        self.append_calls = []

    def append(self, *, block_id, children):
        self.append_calls.append((block_id, children))
        return {"block_id": block_id, "children": children}


class DummyBlocks:
    def __init__(self):
        self.children = DummyBlocksChildren()


class DummyPages:
    def __init__(self):
        self.create_calls = []

    def create(self, *, parent, properties, children):
        payload = {
            "parent": parent,
            "properties": properties,
            "children": children,
        }
        self.create_calls.append(payload)
        return {"id": "page-123", **payload}


class DummyDatabases:
    def __init__(self, response):
        self.response = response
        self.query_calls = []

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self.response


class DummyClient:
    def __init__(self, database_response=None):
        self.pages = DummyPages()
        self.blocks = DummyBlocks()
        self.databases = DummyDatabases(database_response or {"results": []})


@pytest.fixture()
def dummy_client(monkeypatch):
    client = DummyClient()
    monkeypatch.setattr(notion, "_client", lambda: client)
    return client


def test_md_to_blocks_basic():
    blocks = notion._md_to_blocks("# Title\n\nParagraph text\n- Item 1\n- Item 2")
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Title"
    bullet_blocks = [blk for blk in blocks if blk["type"] == "bulleted_list_item"]
    assert len(bullet_blocks) == 2


def test_write_to_notion_appends_existing_page(dummy_client):
    payload = notion.NotionWriteInput(page_id="page", title="ignored", md="content")
    result = notion.write_to_notion(payload)

    assert result["mode"] == "append"
    assert dummy_client.blocks.children.append_calls[0][0] == "page"


def test_write_to_notion_creates_with_parent(dummy_client, monkeypatch):
    monkeypatch.setattr(notion.settings, "notion_parent_page_id", "parent-xyz", raising=False)
    payload = notion.NotionWriteInput(title="Hello", md="Some text")

    result = notion.write_to_notion(payload)

    assert result["mode"] == "create_under_parent"
    assert dummy_client.pages.create_calls[0]["parent"]["page_id"] == "parent-xyz"


def test_sync_database_limits_and_maps(monkeypatch):
    database_response = {
        "results": [{"id": "abc", "url": "https://example"}],
        "next_cursor": "cursor",
        "has_more": True,
    }
    client = DummyClient(database_response=database_response)
    monkeypatch.setattr(notion, "_client", lambda: client)

    payload = notion.NotionSyncInput(db_id="db", page_limit=5)
    result = notion.sync_database(payload)

    assert result["count"] == 1
    assert result["pages"][0]["id"] == "abc"
    assert client.databases.query_calls[0]["database_id"] == "db"
    assert client.databases.query_calls[0]["page_size"] == 5
