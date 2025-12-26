"""Service layer for collaborative whiteboards.

The service keeps revision numbering monotonic, persists AI context alongside
the Excalidraw scene JSON, and provides light comment support so API handlers
stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from alfred.core.utils import utcnow_naive
from alfred.models.whiteboard import Whiteboard, WhiteboardComment, WhiteboardRevision


@dataclass
class WhiteboardService:
    """Encapsulates whiteboard CRUD, revisioning, and comments."""

    session: Session

    # Whiteboards
    def create_whiteboard(
        self,
        *,
        title: str,
        description: str | None = None,
        created_by: str | None = None,
        org_id: str | None = None,
        template_id: str | None = None,
        initial_scene: dict | None = None,
        ai_context: dict | None = None,
        applied_prompt: str | None = None,
    ) -> tuple[Whiteboard, WhiteboardRevision]:
        """Create a board and seed it with an initial revision."""

        board = Whiteboard(
            title=title.strip(),
            description=description.strip() if description else None,
            created_by=created_by.strip() if created_by else None,
            org_id=org_id.strip() if org_id else None,
            template_id=template_id.strip() if template_id else None,
        )
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)

        revision = self.create_revision(
            whiteboard_id=board.id or 0,
            scene_json=initial_scene or {},
            ai_context=ai_context,
            applied_prompt=applied_prompt,
            created_by=created_by,
        )
        return board, revision

    def list_whiteboards(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Whiteboard]:
        """List boards ordered by recency."""

        stmt = select(Whiteboard).order_by(Whiteboard.updated_at.desc()).offset(skip).limit(limit)
        if not include_archived:
            stmt = stmt.where(Whiteboard.is_archived.is_(False))
        return list(self.session.exec(stmt))

    def get_whiteboard(self, board_id: int) -> Whiteboard | None:
        """Fetch a single board by id."""

        return self.session.get(Whiteboard, board_id)

    def update_whiteboard(self, board: Whiteboard, **fields) -> Whiteboard:
        """Apply partial updates and refresh timestamps."""

        if "title" in fields and fields["title"]:
            board.title = str(fields["title"]).strip()
        if "description" in fields:
            board.description = fields["description"]
        if "template_id" in fields:
            board.template_id = fields["template_id"]
        if "is_archived" in fields and fields["is_archived"] is not None:
            board.is_archived = bool(fields["is_archived"])
        board.updated_at = utcnow_naive()
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)
        return board

    # Revisions
    def create_revision(
        self,
        *,
        whiteboard_id: int,
        scene_json: dict,
        ai_context: dict | None = None,
        applied_prompt: str | None = None,
        created_by: str | None = None,
    ) -> WhiteboardRevision:
        """Append a revision with an incremented revision number."""

        board = self.session.get(Whiteboard, whiteboard_id)
        if not board:
            raise ValueError("Whiteboard not found")

        latest_no = self.session.exec(
            select(WhiteboardRevision.revision_no)
            .where(WhiteboardRevision.whiteboard_id == whiteboard_id)
            .order_by(WhiteboardRevision.revision_no.desc())
            .limit(1)
        ).first()
        next_rev = (latest_no or 0) + 1
        revision = WhiteboardRevision(
            whiteboard_id=whiteboard_id,
            revision_no=next_rev,
            scene_json=scene_json,
            ai_context=ai_context,
            applied_prompt=applied_prompt,
            created_by=created_by,
        )
        self.session.add(revision)
        board.updated_at = utcnow_naive()
        self.session.add(board)

        self.session.commit()
        self.session.refresh(revision)
        return revision

    def list_revisions(self, *, whiteboard_id: int) -> list[WhiteboardRevision]:
        """Return all revisions newest first."""

        stmt = (
            select(WhiteboardRevision)
            .where(WhiteboardRevision.whiteboard_id == whiteboard_id)
            .order_by(WhiteboardRevision.revision_no.desc())
        )
        return list(self.session.exec(stmt))

    def latest_revision(self, *, whiteboard_id: int) -> WhiteboardRevision | None:
        """Grab the newest revision for a board."""

        return self.session.exec(
            select(WhiteboardRevision)
            .where(WhiteboardRevision.whiteboard_id == whiteboard_id)
            .order_by(WhiteboardRevision.revision_no.desc())
            .limit(1)
        ).first()

    # Comments
    def add_comment(
        self,
        *,
        whiteboard_id: int,
        body: str,
        element_id: str | None = None,
        author: str | None = None,
    ) -> WhiteboardComment:
        """Attach a comment to a board or specific element."""

        board = self.session.get(Whiteboard, whiteboard_id)
        if not board:
            raise ValueError("Whiteboard not found")

        comment = WhiteboardComment(
            whiteboard_id=whiteboard_id,
            element_id=element_id,
            body=body.strip(),
            author=author.strip() if author else None,
        )
        self.session.add(comment)
        board.updated_at = utcnow_naive()
        self.session.add(board)
        self.session.commit()
        self.session.refresh(comment)
        return comment

    def list_comments(self, *, whiteboard_id: int) -> list[WhiteboardComment]:
        """Return comments newest first."""

        stmt = (
            select(WhiteboardComment)
            .where(WhiteboardComment.whiteboard_id == whiteboard_id)
            .order_by(WhiteboardComment.created_at.desc())
        )
        return list(self.session.exec(stmt))
