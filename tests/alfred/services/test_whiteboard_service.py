from alfred.services.whiteboard_service import WhiteboardService
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_whiteboard_seeds_revision() -> None:
    session = _session()
    service = WhiteboardService(session)

    board, revision = service.create_whiteboard(
        title="Research Flow", initial_scene={"elements": []}
    )

    assert board.id is not None
    assert revision.whiteboard_id == board.id
    assert revision.revision_no == 1
    assert revision.scene_json == {"elements": []}


def test_revisions_increment_and_list() -> None:
    session = _session()
    service = WhiteboardService(session)
    board, _ = service.create_whiteboard(title="Pipeline")

    service.create_revision(whiteboard_id=board.id or 0, scene_json={"a": 1})
    service.create_revision(whiteboard_id=board.id or 0, scene_json={"a": 2})

    revisions = service.list_revisions(whiteboard_id=board.id or 0)
    assert [rev.revision_no for rev in revisions] == [3, 2, 1]
    latest = service.latest_revision(whiteboard_id=board.id or 0)
    assert latest is not None and latest.revision_no == 3


def test_comments_update_board_timestamp() -> None:
    session = _session()
    service = WhiteboardService(session)
    board, _ = service.create_whiteboard(title="Discussion")

    before_update = board.updated_at
    comment = service.add_comment(whiteboard_id=board.id or 0, body="Looks good")
    refreshed = service.get_whiteboard(board.id or 0)

    assert comment.id is not None
    assert refreshed is not None
    assert refreshed.updated_at >= before_update


def test_listing_excludes_archived_by_default() -> None:
    session = _session()
    service = WhiteboardService(session)
    board, _ = service.create_whiteboard(title="Active")
    archived, _ = service.create_whiteboard(title="Old")
    service.update_whiteboard(archived, is_archived=True)

    boards = service.list_whiteboards()
    assert {b.title for b in boards} == {"Active"}

    all_boards = service.list_whiteboards(include_archived=True)
    assert {b.title for b in all_boards} == {"Active", "Old"}
