from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

logger = logging.getLogger(__name__)


def _version_key(v: str | int | float) -> str:
    # Preserve numeric vs string identity.
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class PostgresCheckpointConfig:
    dsn: str
    checkpoints_table: str = "alfred_lg_checkpoints"
    blobs_table: str = "alfred_lg_checkpoint_blobs"
    writes_table: str = "alfred_lg_checkpoint_writes"


class PostgresCheckpointSaver(BaseCheckpointSaver[str]):
    """
    Postgres-backed LangGraph checkpointer (sync).

    This mirrors the core behavior of LangGraph's InMemorySaver, but persists
    checkpoints/blobs/writes in Postgres via psycopg.
    """

    def __init__(self, *, cfg: PostgresCheckpointConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._schema_ready = False

    def _connect(self) -> psycopg.Connection:
        # autocommit keeps code simple; each call is a small transaction.
        conn = psycopg.connect(self.cfg.dsn, autocommit=True)
        return conn

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.cfg.checkpoints_table} (
                          thread_id TEXT NOT NULL,
                          checkpoint_ns TEXT NOT NULL,
                          checkpoint_id TEXT NOT NULL,
                          parent_checkpoint_id TEXT NULL,
                          checkpoint_type TEXT NOT NULL,
                          checkpoint_bytes BYTEA NOT NULL,
                          metadata_type TEXT NOT NULL,
                          metadata_bytes BYTEA NOT NULL,
                          PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                        );
                        """
                    )
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.cfg.blobs_table} (
                          thread_id TEXT NOT NULL,
                          checkpoint_ns TEXT NOT NULL,
                          channel TEXT NOT NULL,
                          version_key TEXT NOT NULL,
                          value_type TEXT NOT NULL,
                          value_bytes BYTEA NOT NULL,
                          PRIMARY KEY (thread_id, checkpoint_ns, channel, version_key)
                        );
                        """
                    )
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.cfg.writes_table} (
                          thread_id TEXT NOT NULL,
                          checkpoint_ns TEXT NOT NULL,
                          checkpoint_id TEXT NOT NULL,
                          task_id TEXT NOT NULL,
                          idx INTEGER NOT NULL,
                          channel TEXT NOT NULL,
                          value_type TEXT NOT NULL,
                          value_bytes BYTEA NOT NULL,
                          task_path TEXT NOT NULL DEFAULT '',
                          PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                        );
                        """
                    )
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("Postgres checkpointer schema init failed: %s", exc)
            return

        self._schema_ready = True

    def _load_blobs(
        self, thread_id: str, checkpoint_ns: str, versions: ChannelVersions
    ) -> dict[str, Any]:
        if not versions:
            return {}
        self._ensure_schema()
        out: dict[str, Any] = {}
        with self._connect() as conn:
            with conn.cursor() as cur:
                for channel, version in versions.items():
                    cur.execute(
                        f"""
                        SELECT value_type, value_bytes
                        FROM {self.cfg.blobs_table}
                        WHERE thread_id = %s AND checkpoint_ns = %s AND channel = %s AND version_key = %s
                        """,
                        (thread_id, checkpoint_ns, channel, _version_key(version)),
                    )
                    row = cur.fetchone()
                    if not row:
                        continue
                    value_type, value_bytes = row
                    if value_type == "empty":
                        continue
                    out[channel] = self.serde.loads_typed((value_type, value_bytes))
        return out

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        self._ensure_schema()
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        where = "thread_id = %s AND checkpoint_ns = %s"
        params: list[Any] = [thread_id, checkpoint_ns]
        if checkpoint_id:
            where += " AND checkpoint_id = %s"
            params.append(checkpoint_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT checkpoint_id, parent_checkpoint_id,
                           checkpoint_type, checkpoint_bytes,
                           metadata_type, metadata_bytes
                    FROM {self.cfg.checkpoints_table}
                    WHERE {where}
                    ORDER BY checkpoint_id DESC
                    LIMIT 1
                    """,
                    params,
                )
                row = cur.fetchone()
                if not row:
                    return None
                (
                    selected_checkpoint_id,
                    parent_checkpoint_id,
                    checkpoint_type,
                    checkpoint_bytes,
                    metadata_type,
                    metadata_bytes,
                ) = row

                checkpoint_: Checkpoint = self.serde.loads_typed(
                    (checkpoint_type, checkpoint_bytes)
                )
                checkpoint_full: Checkpoint = {
                    **checkpoint_,
                    "channel_values": self._load_blobs(
                        thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                    ),
                }

                cur.execute(
                    f"""
                    SELECT task_id, idx, channel, value_type, value_bytes, task_path
                    FROM {self.cfg.writes_table}
                    WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                    ORDER BY task_id, idx
                    """,
                    (thread_id, checkpoint_ns, selected_checkpoint_id),
                )
                pending: list[PendingWrite] = []
                for task_id, idx, channel, value_type, value_bytes, task_path in cur.fetchall():
                    _ = task_path  # not currently surfaced in CheckpointTuple
                    pending.append(
                        (task_id, channel, self.serde.loads_typed((value_type, value_bytes)))
                    )

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": selected_checkpoint_id,
                }
            },
            checkpoint=checkpoint_full,
            metadata=self.serde.loads_typed((metadata_type, metadata_bytes)),
            pending_writes=pending,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        _ = filter
        self._ensure_schema()
        if config is None:
            return iter(())

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        before_id = get_checkpoint_id(before) if before else None
        max_rows = limit or 50

        where = "thread_id = %s AND checkpoint_ns = %s"
        params: list[Any] = [thread_id, checkpoint_ns]
        if before_id:
            where += " AND checkpoint_id < %s"
            params.append(before_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT checkpoint_id
                    FROM {self.cfg.checkpoints_table}
                    WHERE {where}
                    ORDER BY checkpoint_id DESC
                    LIMIT %s
                    """,
                    [*params, max_rows],
                )
                ids = [r[0] for r in cur.fetchall()]

        def _iter() -> Iterator[CheckpointTuple]:
            for cid in ids:
                tup = self.get_tuple(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": cid,
                        }
                    }
                )
                if tup is not None:
                    yield tup

        return _iter()

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        self._ensure_schema()
        c = checkpoint.copy()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        values: dict[str, Any] = c.pop("channel_values")  # type: ignore[misc]

        with self._connect() as conn:
            with conn.cursor() as cur:
                for channel, version in new_versions.items():
                    v = values.get(channel)
                    value_type, value_bytes = (
                        self.serde.dumps_typed(v) if channel in values else ("empty", b"")
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {self.cfg.blobs_table}
                          (thread_id, checkpoint_ns, channel, version_key, value_type, value_bytes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (thread_id, checkpoint_ns, channel, version_key)
                        DO UPDATE SET value_type = EXCLUDED.value_type, value_bytes = EXCLUDED.value_bytes
                        """,
                        (
                            thread_id,
                            checkpoint_ns,
                            channel,
                            _version_key(version),
                            value_type,
                            value_bytes,
                        ),
                    )

                checkpoint_type, checkpoint_bytes = self.serde.dumps_typed(c)
                metadata_type, metadata_bytes = self.serde.dumps_typed(
                    get_checkpoint_metadata(config, metadata)
                )
                cur.execute(
                    f"""
                    INSERT INTO {self.cfg.checkpoints_table}
                      (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                       checkpoint_type, checkpoint_bytes, metadata_type, metadata_bytes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
                    DO UPDATE SET
                      parent_checkpoint_id = EXCLUDED.parent_checkpoint_id,
                      checkpoint_type = EXCLUDED.checkpoint_type,
                      checkpoint_bytes = EXCLUDED.checkpoint_bytes,
                      metadata_type = EXCLUDED.metadata_type,
                      metadata_bytes = EXCLUDED.metadata_bytes
                    """,
                    (
                        thread_id,
                        checkpoint_ns,
                        checkpoint["id"],
                        parent_checkpoint_id,
                        checkpoint_type,
                        checkpoint_bytes,
                        metadata_type,
                        metadata_bytes,
                    ),
                )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self._ensure_schema()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        with self._connect() as conn:
            with conn.cursor() as cur:
                for idx, (channel, value) in enumerate(writes):
                    write_idx = WRITES_IDX_MAP.get(channel, idx)
                    if write_idx >= 0:
                        cur.execute(
                            f"""
                            SELECT 1
                            FROM {self.cfg.writes_table}
                            WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s
                              AND task_id = %s AND idx = %s
                            """,
                            (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx),
                        )
                        if cur.fetchone():
                            continue

                    value_type, value_bytes = self.serde.dumps_typed(value)
                    cur.execute(
                        f"""
                        INSERT INTO {self.cfg.writes_table}
                          (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value_type, value_bytes, task_path)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                        DO NOTHING
                        """,
                        (
                            thread_id,
                            checkpoint_ns,
                            checkpoint_id,
                            task_id,
                            write_idx,
                            channel,
                            value_type,
                            value_bytes,
                            task_path or "",
                        ),
                    )

    def delete_thread(self, thread_id: str) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.cfg.writes_table} WHERE thread_id = %s", (thread_id,)
                )
                cur.execute(
                    f"DELETE FROM {self.cfg.checkpoints_table} WHERE thread_id = %s", (thread_id,)
                )
                cur.execute(
                    f"DELETE FROM {self.cfg.blobs_table} WHERE thread_id = %s", (thread_id,)
                )


__all__ = ["PostgresCheckpointConfig", "PostgresCheckpointSaver"]
