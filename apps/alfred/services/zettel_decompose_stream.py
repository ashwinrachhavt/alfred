"""Streaming decomposition orchestrator.

Decomposes a raw paragraph into atomic zettel candidate cards and streams
them one-at-a-time via SSE. Does NOT persist anything — the caller reviews,
edits, and later commits via T7's `/bulk-from-decomposition` endpoint.

SSE events (in order):
  decompose_started     {"raw_char_count": int, "shared_topic": str | None}
  decompose_thinking    {"content": str}              # 0..N (reasoning tokens)
  candidate_ready       {"index": int, "title": ..., "content": ..., ...}  # per candidate
  decompose_complete    {"total_candidates": int}
  error                 {"step": str, "message": str}  # on failure
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Request
from sqlmodel import Session

from alfred.core.settings import settings
from alfred.schemas.zettel import ZettelDecomposeRequest
from alfred.services.sse_base import SSEStreamOrchestrator

logger = logging.getLogger(__name__)


# Re-export the base class's static _sse at module level so tests / callers
# can `from alfred.services.zettel_decompose_stream import _sse` in the same
# way they do for zettel_creation_stream.
_sse = SSEStreamOrchestrator._sse


class ZettelDecomposeStream(SSEStreamOrchestrator):
    """Stream atomic-card candidates decomposed from a raw paragraph."""

    MAX_CANDIDATES = 15
    MIN_CONTENT_LEN = 120
    INPUT_CHAR_LIMIT = 16_000

    # Redis key prefix for idempotency; value is the latest sha256[:16] the
    # given session_id (or 'anon') has submitted. A stream aborts as soon as
    # it sees a different value under this key.
    _REDIS_KEY_PREFIX = "decompose:latest:"
    _REDIS_TTL_SECONDS = 300

    def __init__(
        self,
        payload: ZettelDecomposeRequest,
        request: Request | None = None,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(request=request, db_session_factory=db_session_factory)
        self.payload = payload
        # Truncate oversized input; the user's flow is a paste, not a book upload.
        self._raw = (payload.raw_text or "")[: self.INPUT_CHAR_LIMIT]
        self._hash = hashlib.sha256(f"{payload.session_id}|{self._raw}".encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def _redis_key(self) -> str:
        sid = self.payload.session_id if self.payload.session_id is not None else "anon"
        return f"{self._REDIS_KEY_PREFIX}{sid}"

    def _make_stale_checker(self) -> Callable[[], bool]:
        """Return a zero-arg callable returning True once a newer request
        has superseded this one.

        Stores ``self._hash`` under a session-scoped Redis key with a 300s
        TTL. The stale-check reads the current value; if it no longer matches
        ``self._hash``, returns True. If Redis is unavailable at any point we
        degrade gracefully to ``lambda: False``.
        """
        try:
            from alfred.core.redis_client import get_redis_client

            redis = get_redis_client()
        except Exception:
            logger.debug("Redis import failed; skipping idempotency", exc_info=True)
            return lambda: False

        if redis is None:
            return lambda: False

        key = self._redis_key()
        try:
            redis.set(key, self._hash, ex=self._REDIS_TTL_SECONDS)
        except Exception:
            logger.debug("Redis set failed; skipping idempotency", exc_info=True)
            return lambda: False

        def _is_stale() -> bool:
            try:
                current = redis.get(key)
            except Exception:
                logger.debug("Redis get failed; treating as not-stale", exc_info=True)
                return False
            if current is None:
                # TTL expired or key evicted. Not stale — this is still the
                # same request from the client's POV.
                return False
            return current != self._hash

        return _is_stale

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_decompose_prompt(self) -> list[dict[str, str]]:
        """Build the system+user messages for the decomposition LLM call."""
        system = (
            "You are a Zettelkasten decomposition engine. Break raw knowledge "
            "into coherent block-sized cards — one meaningful block of thought "
            "per card.\n\n"
            "Atomicity contract:\n"
            "- ONE coherent block per card. A block may contain a claim, its "
            "  supporting reasoning, and one concrete example or implication.\n"
            "- Do NOT split sentence-by-sentence. If adjacent sentences explain "
            "  the same claim, preserve them together in one card.\n"
            "- Split only when two blocks naturally stand alone and would be "
            "  useful to review independently.\n"
            "- The title IS the idea, expressed as a crisp claim — not a label. "
            "  Do not write category names like 'Introduction' or 'Background'.\n"
            "- Body is 3-6 sentences of supporting detail the title alone can't "
            "  carry. Prefer concrete evidence, examples, and implications over "
            "  restating the title.\n"
            "- Assign Bloom's Taxonomy level 1-6 per card (1 Remember, "
            "  2 Understand, 3 Apply, 4 Analyze, 5 Evaluate, 6 Create). Pick the "
            "  LOWEST level that honestly fits.\n"
            "- Tags: a short list of lowercase keywords. 2-5 per card.\n"
            "- Sibling links: if a candidate directly builds on, contrasts "
            "  with, or exemplifies another candidate IN THIS SAME RESPONSE, "
            "  list that candidate's index in `links_to_siblings`. Indexes are "
            "  0-based and refer to the order in which candidates appear in "
            "  your output. Do NOT reference cards outside this response.\n\n"
            "Hard constraints:\n"
            "- Cap at 15 cards. Reject over-splits — if you would produce a "
            "  candidate with less than 120 characters of content, merge it "
            "  into an adjacent candidate or skip it.\n"
            "- Do NOT repeat content across cards. Each card earns its place.\n\n"
            "Respond ONLY with valid JSON (no markdown fences, no commentary). "
            "Shape:\n"
            "{\n"
            '  "candidates": [\n'
            "    {\n"
            '      "title": "...",\n'
            '      "content": "...",\n'
            '      "bloom_level": 2,\n'
            '      "bloom_rationale": "short sentence explaining the level",\n'
            '      "tags": ["tag1", "tag2"],\n'
            '      "links_to_siblings": [1, 3]\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user_parts = [f"Raw text to decompose:\n---\n{self._raw}\n---"]
        if self.payload.shared_topic:
            user_parts.append(f"\nAll candidates share this topic: {self.payload.shared_topic}.")
        user = "\n".join(user_parts)

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _filter_and_normalize(self, raw: list[Any]) -> list[dict[str, Any]]:
        """Drop under-length candidates, cap the tail, and normalise fields.

        Returns candidates in the order they appeared (kept indexes only).
        ``links_to_siblings`` is sanitised after filtering: only indexes that
        point to a KEPT candidate, and never self, survive.
        """
        # Pass 1: coerce to dicts, drop non-dicts.
        dict_candidates: list[dict[str, Any]] = [c for c in raw if isinstance(c, dict)]

        # Pass 2: filter out short-content candidates.
        kept: list[dict[str, Any]] = []
        for c in dict_candidates:
            content = str(c.get("content") or "").strip()
            if len(content) < self.MIN_CONTENT_LEN:
                continue
            kept.append(c)

        # Pass 3: cap the tail at MAX_CANDIDATES.
        kept = kept[: self.MAX_CANDIDATES]

        # Pass 4: normalise each field and sanitise sibling links.
        normalised: list[dict[str, Any]] = []
        n = len(kept)
        for self_index, c in enumerate(kept):
            content = str(c.get("content") or "").strip()

            raw_title = c.get("title")
            if raw_title is not None:
                title = str(raw_title).strip()
            else:
                title = ""
            if not title:
                # Fall back to the first sentence of the content.
                first_sentence = content.split(".", 1)[0].strip()
                title = first_sentence or content[:80]
            title = title[:255]

            try:
                bloom_level = int(c.get("bloom_level", 1))
            except (TypeError, ValueError):
                bloom_level = 1
            bloom_level = max(1, min(6, bloom_level))

            bloom_rationale = str(c.get("bloom_rationale") or "").strip()

            raw_tags = c.get("tags") or []
            tags: list[str] = []
            seen: set[str] = set()
            if isinstance(raw_tags, list):
                for t in raw_tags:
                    if not isinstance(t, str):
                        continue
                    norm = t.strip().lower()
                    if not norm or norm in seen:
                        continue
                    seen.add(norm)
                    tags.append(norm)

            raw_links = c.get("links_to_siblings") or []
            links: list[int] = []
            if isinstance(raw_links, list):
                for idx in raw_links:
                    try:
                        i = int(idx)
                    except (TypeError, ValueError):
                        continue
                    if i < 0 or i >= n:
                        continue
                    if i == self_index:
                        continue
                    if i in links:
                        continue
                    links.append(i)

            normalised.append(
                {
                    "title": title,
                    "content": content,
                    "bloom_level": bloom_level,
                    "bloom_rationale": bloom_rationale,
                    "tags": tags,
                    "links_to_siblings": links,
                }
            )
        return normalised

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self) -> AsyncGenerator[str, None]:
        if not self._raw.strip():
            yield self._sse(
                "error",
                {"step": "decompose_input", "message": "raw_text is empty"},
            )
            return

        # Idempotency: Redis remembers the latest hash this session sent.
        is_stale = self._make_stale_checker()

        yield self._sse(
            "decompose_started",
            {
                "raw_char_count": len(self._raw),
                "shared_topic": self.payload.shared_topic,
            },
        )

        messages = self._build_decompose_prompt()
        model = settings.zettel_analysis_model

        completion_buffer = ""
        try:
            async for kind, content in self._run_openai_stream_with_reasoning(
                messages=messages,
                model=model,
                max_completion_tokens=4096,
                is_stale=is_stale,
            ):
                if kind == "thinking":
                    yield self._sse("decompose_thinking", {"content": content})
                else:
                    completion_buffer += content
        except Exception as exc:
            logger.warning("Decompose stream failed: %s", exc, exc_info=True)
            yield self._sse("error", {"step": "decompose_llm", "message": str(exc)})
            return

        # If another request superseded us while streaming, drop out without
        # emitting a completion event.
        if await self._is_disconnected_or_stale(is_stale):
            return

        parsed = self._parse_structured_json(completion_buffer)
        if parsed is None:
            yield self._sse(
                "error",
                {"step": "decompose_parse", "message": "LLM returned malformed JSON"},
            )
            return

        raw_candidates = parsed.get("candidates") or []
        if not isinstance(raw_candidates, list):
            raw_candidates = []

        candidates = self._filter_and_normalize(raw_candidates)
        for i, candidate in enumerate(candidates):
            event_payload = {"index": i, **candidate}
            yield self._sse("candidate_ready", event_payload)

        yield self._sse(
            "decompose_complete",
            {"total_candidates": len(candidates)},
        )
