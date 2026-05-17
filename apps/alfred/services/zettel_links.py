"""Zettel link row management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, TypeAlias

from sqlmodel import Session, select

from alfred.models.zettel import ZettelLink


class _UnsetType:
    """Sentinel for patch fields where ``None`` is a real value."""


UNSET: Final = _UnsetType()
LinkContextPatch: TypeAlias = str | None | _UnsetType


@dataclass
class ZettelLinkService:
    """Create, delete, and patch graph link rows."""

    session: Session

    def create_link(
        self,
        *,
        from_card_id: int,
        to_card_id: int,
        type: str = "reference",
        context: str | None = None,
        bidirectional: bool = True,
    ) -> list[ZettelLink]:
        normalized = type.strip().lower()
        if not normalized:
            raise ValueError("Link type cannot be empty")

        links: list[ZettelLink] = []
        existing = self.session.exec(
            select(ZettelLink).where(
                (ZettelLink.from_card_id == from_card_id)
                & (ZettelLink.to_card_id == to_card_id)
                & (ZettelLink.type == normalized)
            )
        ).first()
        if not existing:
            links.append(
                ZettelLink(
                    from_card_id=from_card_id,
                    to_card_id=to_card_id,
                    type=normalized,
                    context=context,
                    bidirectional=bidirectional,
                )
            )

        if bidirectional:
            reverse_exists = self.session.exec(
                select(ZettelLink).where(
                    (ZettelLink.from_card_id == to_card_id)
                    & (ZettelLink.to_card_id == from_card_id)
                    & (ZettelLink.type == normalized)
                )
            ).first()
            if not reverse_exists:
                links.append(
                    ZettelLink(
                        from_card_id=to_card_id,
                        to_card_id=from_card_id,
                        type=normalized,
                        context=context,
                        bidirectional=bidirectional,
                    )
                )

        for link in links:
            self.session.add(link)
        self.session.commit()
        for link in links:
            self.session.refresh(link)
        return links

    def list_links(self, *, card_id: int) -> list[ZettelLink]:
        stmt = select(ZettelLink).where(
            (ZettelLink.from_card_id == card_id) | (ZettelLink.to_card_id == card_id)
        )
        return list(self.session.exec(stmt))

    def delete_link(self, link_id: int) -> bool:
        """Delete a link by ID. Returns True if deleted, False if not found."""
        link = self.session.get(ZettelLink, link_id)
        if not link:
            return False

        if link.bidirectional:
            reverse = self.session.exec(
                select(ZettelLink).where(
                    (ZettelLink.from_card_id == link.to_card_id)
                    & (ZettelLink.to_card_id == link.from_card_id)
                    & (ZettelLink.type == link.type)
                )
            ).first()
            if reverse:
                self.session.delete(reverse)

        self.session.delete(link)
        self.session.commit()
        return True

    def update_link(
        self,
        link_id: int,
        *,
        type: str | None = None,
        context: LinkContextPatch = UNSET,
        bidirectional: bool | None = None,
    ) -> ZettelLink | None:
        """Patch a link and synchronize the reverse row."""
        link = self.session.get(ZettelLink, link_id)
        if not link:
            return None

        normalized_type: str | None = None
        if type is not None:
            normalized_type = type.strip().lower()
            if not normalized_type:
                raise ValueError("Link type cannot be empty")

        reverse = self.session.exec(
            select(ZettelLink).where(
                (ZettelLink.from_card_id == link.to_card_id)
                & (ZettelLink.to_card_id == link.from_card_id)
                & (ZettelLink.type == link.type)
            )
        ).first()

        if normalized_type is not None and normalized_type != link.type:
            collision = self.session.exec(
                select(ZettelLink).where(
                    (ZettelLink.from_card_id == link.from_card_id)
                    & (ZettelLink.to_card_id == link.to_card_id)
                    & (ZettelLink.type == normalized_type)
                    & (ZettelLink.id != link.id)
                )
            ).first()
            if collision:
                self.session.delete(collision)

            reverse_collision = None
            if reverse:
                reverse_collision = self.session.exec(
                    select(ZettelLink).where(
                        (ZettelLink.from_card_id == reverse.from_card_id)
                        & (ZettelLink.to_card_id == reverse.to_card_id)
                        & (ZettelLink.type == normalized_type)
                        & (ZettelLink.id != reverse.id)
                    )
                ).first()
                if reverse_collision:
                    self.session.delete(reverse_collision)

            if collision or reverse_collision:
                self.session.flush()
            link.type = normalized_type
            if reverse:
                reverse.type = normalized_type

        if not isinstance(context, _UnsetType):
            link.context = context
            if reverse:
                reverse.context = context

        if bidirectional is not None and bidirectional != link.bidirectional:
            link.bidirectional = bidirectional
            if reverse:
                reverse.bidirectional = bidirectional
            if bidirectional and reverse is None:
                self.session.add(
                    ZettelLink(
                        from_card_id=link.to_card_id,
                        to_card_id=link.from_card_id,
                        type=link.type,
                        context=link.context,
                        bidirectional=True,
                    )
                )
            elif not bidirectional and reverse is not None:
                self.session.delete(reverse)

        self.session.commit()
        self.session.refresh(link)
        return link
