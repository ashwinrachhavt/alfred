from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from alfred.core.exceptions import (
    AlfredException,
    NotFoundError,
    ShareAccessDeniedError,
    ShareExpiredError,
)
from alfred.core.settings import settings
from alfred.core.utils import utcnow as _utcnow
from alfred.schemas.system_design import (
    AutosaveRequest,
    ComponentDefinition,
    DiagramExport,
    DiagramExportRequest,
    DiagramVersion,
    ExcalidrawData,
    ScaleEstimateRequest,
    ScaleEstimateResponse,
    SystemDesignArtifacts,
    SystemDesignKnowledgeDraft,
    SystemDesignSession,
    SystemDesignSessionCreate,
    SystemDesignSessionSummary,
    SystemDesignSessionUpdate,
    SystemDesignShareSettings,
    SystemDesignShareUpdate,
    SystemDesignTemplateCreate,
    TemplateDefinition,
)
from alfred.services.datastore import DataStoreService
from alfred.services.llm_service import LLMService
from alfred.services.system_design_heuristics import component_library, template_library
from alfred.services.system_design_share import hash_password, verify_password


def _new_id() -> str:
    return uuid.uuid4().hex


MAX_AUTOSAVE_RETRIES = 5


class SystemDesignSessionVersionConflictError(AlfredException):
    """Raised when a client attempts to update a stale diagram version."""

    status_code = 409
    default_code = "system_design_session_version_conflict"


def _coerce_version(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 1
    return parsed if parsed >= 1 else 1


@dataclass
class SystemDesignService:
    """Postgres-backed storage and heuristics for system design interviews."""

    collection_name: str = settings.system_design_sessions_collection
    templates_collection_name: str | None = None
    llm_service: LLMService | None = None

    def __post_init__(self) -> None:
        self._collection = DataStoreService(default_collection=self.collection_name)
        templates_collection = self.templates_collection_name or f"{self.collection_name}_templates"
        self._templates = DataStoreService(default_collection=templates_collection)

    def ensure_indexes(self) -> None:
        return

    def component_library(self) -> list[ComponentDefinition]:
        return component_library()

    def template_library(self) -> list[TemplateDefinition]:
        return template_library()

    def list_templates(self) -> list[TemplateDefinition]:
        """Return both built-in and user-saved templates."""

        builtins = self.template_library()
        custom_docs = self._templates.find_many({})
        custom = [self._to_template(str(doc["_id"]), doc) for doc in custom_docs]
        return builtins + custom

    def get_template(self, template_id: str) -> TemplateDefinition | None:
        for template in self.template_library():
            if template.id == template_id:
                return template
        doc = self._templates.find_one({"_id": template_id})
        if not doc:
            return None
        return self._to_template(str(doc["_id"]), doc)

    def create_template(self, payload: SystemDesignTemplateCreate) -> TemplateDefinition:
        now = _utcnow()
        doc = {
            "name": payload.name,
            "description": payload.description,
            "components": payload.components,
            "diagram": payload.diagram.model_dump(by_alias=True),
            "created_at": now,
            "updated_at": now,
        }
        doc_id = self._templates.insert_one(doc)
        return self._to_template(doc_id, doc | {"_id": doc_id})

    def create_session(self, payload: SystemDesignSessionCreate) -> SystemDesignSession:
        now = _utcnow()
        share_id = _new_id()

        diagram = ExcalidrawData(elements=[], appState={}, files={}, metadata={})
        template_id = payload.template_id
        if template_id:
            template = self.get_template(template_id)
            if template is not None:
                diagram = template.diagram
            else:
                template_id = None

        doc = {
            "share_id": share_id,
            "share_settings": SystemDesignShareSettings().model_dump(),
            "share_secret": {},
            "title": payload.title,
            "problem_statement": payload.problem_statement,
            "template_id": template_id,
            "notes_markdown": "",
            "diagram": diagram.model_dump(by_alias=True),
            "version": 1,
            "versions": [],
            "exports": [],
            "artifacts": SystemDesignArtifacts().model_dump(),
            "metadata": payload.metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        doc_id = self._collection.insert_one(doc)
        return self._to_session(doc_id, doc)

    def get_session(self, session_id: str) -> SystemDesignSession | None:
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def list_sessions(self, *, limit: int = 20) -> list[SystemDesignSessionSummary]:
        docs = self._collection.find_many(
            {},
            sort=[("updated_at", -1)],
            limit=limit,
        )
        return [self._to_session_summary(str(doc.get("_id", "")), doc) for doc in docs]

    def update_session(
        self, session_id: str, payload: SystemDesignSessionUpdate
    ) -> SystemDesignSession | None:
        now = _utcnow()
        update: dict[str, Any] = {"updated_at": now}
        if payload.title is not None:
            update["title"] = payload.title
        if payload.problem_statement is not None:
            update["problem_statement"] = payload.problem_statement

        self._collection.update_one(
            {"_id": session_id},
            {"$set": update},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def get_by_share_id(self, share_id: str) -> SystemDesignSession | None:
        doc = self._collection.find_one({"share_id": share_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def get_shared_session(self, share_id: str, *, password: str | None = None) -> SystemDesignSession:
        doc = self._collection.find_one({"share_id": share_id})
        if not doc:
            raise NotFoundError("Session not found.")

        share_settings = SystemDesignShareSettings.model_validate(doc.get("share_settings") or {})
        if not share_settings.enabled:
            raise NotFoundError("Session not found.")

        now = _utcnow()
        if share_settings.expires_at and share_settings.expires_at <= now:
            raise ShareExpiredError("Share link has expired.")

        secret = doc.get("share_secret") if isinstance(doc.get("share_secret"), dict) else {}
        salt_hex = secret.get("password_salt")
        digest_hex = secret.get("password_hash")
        if isinstance(salt_hex, str) and isinstance(digest_hex, str) and digest_hex:
            if not password:
                raise ShareAccessDeniedError("Password required to view this diagram.")
            if not verify_password(password, salt_hex=salt_hex, digest_hex=digest_hex):
                raise ShareAccessDeniedError("Invalid password.")

        return self._to_session(str(doc["_id"]), doc)

    def update_share_settings(
        self, session_id: str, payload: SystemDesignShareUpdate
    ) -> SystemDesignSession | None:
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None

        now = _utcnow()
        share_settings = dict(doc.get("share_settings") or {})
        if payload.enabled is not None:
            share_settings["enabled"] = payload.enabled
        if "expires_at" in payload.model_fields_set:
            share_settings["expires_at"] = payload.expires_at

        secret = dict(doc.get("share_secret") or {})
        if payload.rotate_share_id:
            doc["share_id"] = _new_id()

        should_clear_password = payload.clear_password or (
            "password" in payload.model_fields_set and not (payload.password or "").strip()
        )
        if should_clear_password:
            secret.pop("password_salt", None)
            secret.pop("password_hash", None)
        elif "password" in payload.model_fields_set and payload.password:
            hashed = hash_password(payload.password)
            secret["password_salt"] = hashed.salt_hex
            secret["password_hash"] = hashed.digest_hex

        update: dict[str, Any] = {
            "share_id": doc.get("share_id"),
            "share_settings": share_settings,
            "share_secret": secret,
            "updated_at": now,
        }
        self._collection.update_one({"_id": session_id}, {"$set": update})
        updated = self._collection.find_one({"_id": session_id})
        if not updated:
            return None
        return self._to_session(str(updated["_id"]), updated)

    def autosave(self, session_id: str, payload: AutosaveRequest) -> SystemDesignSession | None:
        now = _utcnow()
        attempts = 0
        while attempts < MAX_AUTOSAVE_RETRIES:
            attempts += 1
            doc = self._collection.find_one({"_id": session_id})
            if not doc:
                return None

            current_version = _coerce_version(doc.get("version", 1))
            if payload.expected_version is not None and payload.expected_version != current_version:
                raise SystemDesignSessionVersionConflictError(
                    "Session has been updated since you last loaded it.",
                    details={
                        "expected_version": payload.expected_version,
                        "actual_version": current_version,
                    },
                )

            next_version = current_version + 1
            update: dict[str, Any] = {
                "diagram": payload.diagram.model_dump(by_alias=True),
                "updated_at": now,
                "version": next_version,
            }
            ops: dict[str, Any] = {"$set": update}
            if payload.label:
                snapshot = DiagramVersion(
                    id=_new_id(),
                    created_at=now,
                    label=payload.label,
                    diagram=payload.diagram,
                )
                ops["$push"] = {"versions": snapshot.model_dump()}

            result = self._collection.update_one(
                {"_id": session_id, "version": current_version},
                ops,
            )
            if result.get("matched_count") == 1:
                saved = self._collection.find_one({"_id": session_id})
                if not saved:
                    return None
                return self._to_session(str(saved.get("_id", session_id)), saved)

            if payload.expected_version is not None:
                raise SystemDesignSessionVersionConflictError(
                    "Session has been updated since you last saved it.",
                    details={
                        "expected_version": payload.expected_version,
                        "actual_version": current_version,
                    },
                )

        raise SystemDesignSessionVersionConflictError(
            "Failed to save diagram due to concurrent updates. Please retry.",
        )

    def update_notes(self, session_id: str, notes_markdown: str) -> SystemDesignSession | None:
        now = _utcnow()
        self._collection.update_one(
            {"_id": session_id},
            {"$set": {"notes_markdown": notes_markdown, "updated_at": now}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def list_versions(self, session_id: str) -> list[DiagramVersion]:
        session = self.get_session(session_id)
        if not session:
            return []
        return session.versions

    def knowledge_draft(self, session: SystemDesignSession) -> SystemDesignKnowledgeDraft:
        return SystemDesignKnowledgeDraft(
            topics=[],
            zettels=[],
            notes=[
                f"Problem: {session.problem_statement}",
                "Capture key assumptions, constraints, and tradeoffs as you iterate.",
            ],
        )

    def add_export(
        self, session_id: str, payload: DiagramExportRequest
    ) -> SystemDesignSession | None:
        now = _utcnow()
        export = DiagramExport(
            id=_new_id(),
            format=payload.format,
            storage_url=payload.storage_url,
            notes=payload.notes,
            created_at=now,
        )
        self._collection.update_one(
            {"_id": session_id},
            {"$push": {"exports": export.model_dump()}, "$set": {"updated_at": now}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc.get("_id", session_id)), doc)

    def attach_artifacts(
        self, session_id: str, artifacts: SystemDesignArtifacts
    ) -> SystemDesignSession | None:
        now = _utcnow()
        data = artifacts.model_dump()
        data["published_at"] = data.get("published_at") or now
        self._collection.update_one(
            {"_id": session_id},
            {"$set": {"artifacts": data, "updated_at": now}},
        )
        doc = self._collection.find_one({"_id": session_id})
        if not doc:
            return None
        return self._to_session(str(doc["_id"]), doc)

    def estimate_scale(self, payload: ScaleEstimateRequest) -> ScaleEstimateResponse:
        inbound_mbps = (payload.qps * payload.avg_request_kb * 8) / 1024
        outbound_mbps = (payload.qps * payload.avg_response_kb * 8) / 1024
        writes_per_day = int(payload.qps * (payload.write_percentage / 100) * 86400)
        storage_gb_per_day = (
            writes_per_day * payload.storage_per_write_kb / (1024 * 1024)
        ) * payload.replication_factor
        retained_storage_gb = storage_gb_per_day * payload.retention_days
        return ScaleEstimateResponse(
            inbound_mbps=round(inbound_mbps, 2),
            outbound_mbps=round(outbound_mbps, 2),
            writes_per_day=writes_per_day,
            storage_gb_per_day=round(storage_gb_per_day, 2),
            retained_storage_gb=round(retained_storage_gb, 2),
        )

    def _to_session(self, session_id: str, doc: dict[str, Any]) -> SystemDesignSession:
        diagram = ExcalidrawData.model_validate(doc.get("diagram") or {})
        version = _coerce_version(doc.get("version", 1))
        versions = [
            DiagramVersion.model_validate(v)
            for v in (doc.get("versions") or [])
            if isinstance(v, dict)
        ]
        exports = [
            DiagramExport.model_validate(v)
            for v in (doc.get("exports") or [])
            if isinstance(v, dict)
        ]
        artifacts = SystemDesignArtifacts.model_validate(doc.get("artifacts") or {})
        share_settings = SystemDesignShareSettings.model_validate(doc.get("share_settings") or {})
        secret = doc.get("share_secret") if isinstance(doc.get("share_secret"), dict) else {}
        share_settings.has_password = bool(secret.get("password_hash"))
        return SystemDesignSession(
            id=session_id,
            share_id=doc.get("share_id", ""),
            share_settings=share_settings,
            title=doc.get("title"),
            problem_statement=doc.get("problem_statement", ""),
            template_id=doc.get("template_id"),
            notes_markdown=doc.get("notes_markdown"),
            diagram=diagram,
            version=version,
            versions=versions,
            exports=exports,
            artifacts=artifacts,
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
            metadata=doc.get("metadata") or {},
        )

    def _to_session_summary(
        self, session_id: str, doc: dict[str, Any]
    ) -> SystemDesignSessionSummary:
        return SystemDesignSessionSummary(
            id=session_id,
            share_id=doc.get("share_id", ""),
            title=doc.get("title"),
            problem_statement=doc.get("problem_statement", ""),
            template_id=doc.get("template_id"),
            version=_coerce_version(doc.get("version", 1)),
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
        )

    def _to_template(self, template_id: str, doc: dict[str, Any]) -> TemplateDefinition:
        diagram = ExcalidrawData.model_validate(doc.get("diagram") or {})
        components = doc.get("components") if isinstance(doc.get("components"), list) else []
        return TemplateDefinition(
            id=template_id,
            name=str(doc.get("name") or "Untitled template"),
            description=str(doc.get("description") or ""),
            components=[str(c) for c in components if isinstance(c, str | int)],
            diagram=diagram,
        )
