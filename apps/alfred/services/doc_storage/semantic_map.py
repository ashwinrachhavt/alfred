"""Semantic map helpers for Explorer (Atheneum) views."""

from __future__ import annotations

import hashlib
from typing import Any


def _hsl_to_hex(*, hue: float, saturation: float, lightness: float) -> str:
    """Convert HSL (0-360, 0-1, 0-1) to hex RGB string."""

    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, float(v)))

    h = (float(hue) % 360.0) / 360.0
    s = _clamp(saturation)
    light = _clamp(lightness)

    def _hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = light
    else:
        q = light * (1 + s) if light < 0.5 else light + s - light * s
        p = 2 * light - q
        r = _hue_to_rgb(p, q, h + 1 / 3)
        g = _hue_to_rgb(p, q, h)
        b = _hue_to_rgb(p, q, h - 1 / 3)

    return "#{:02x}{:02x}{:02x}".format(
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )


def topic_to_color(topic: str | None) -> str:
    """Deterministically map a topic string to a restrained, stable color."""

    topic_norm = (topic or "unknown").strip().lower()
    digest = hashlib.sha1(topic_norm.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return _hsl_to_hex(hue=float(hue), saturation=0.62, lightness=0.52)


def extract_embedding(row_embedding: Any, row_enrichment: Any) -> list[float] | None:
    """Best-effort extraction of a float embedding from known shapes."""

    if isinstance(row_embedding, list) and row_embedding:
        try:
            return [float(x) for x in row_embedding]
        except Exception:
            return None

    if isinstance(row_enrichment, dict):
        emb = row_enrichment.get("embedding")
        if isinstance(emb, list) and emb:
            try:
                return [float(x) for x in emb]
            except Exception:
                return None

    return None


def project_vectors_to_3d(vectors: list[list[float]]) -> list[list[float]]:
    """Reduce high-dimensional vectors to 3D coordinates."""

    if not vectors:
        return []

    if len(vectors) == 1:
        return [[0.0, 0.0, 0.0]]
    if len(vectors) == 2:
        return [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]

    import numpy as np
    from sklearn.decomposition import PCA

    dim = len(vectors[0])
    same_dim = [v for v in vectors if isinstance(v, list) and len(v) == dim]
    if len(same_dim) < 3:
        return [[0.0, 0.0, 0.0] for _ in vectors]

    mat = np.asarray(same_dim, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] < 3:
        return [[0.0, 0.0, 0.0] for _ in vectors]

    mat = np.where(np.isfinite(mat), mat, 0.0).astype(np.float32, copy=False)

    pca = PCA(n_components=3)
    coords = pca.fit_transform(mat)
    coords = coords - np.mean(coords, axis=0, keepdims=True)

    norms = np.linalg.norm(coords, axis=1)
    max_norm = float(np.max(norms)) if coords.shape[0] else 1.0
    if max_norm > 0:
        coords = coords / max_norm

    return [[float(row[0]), float(row[1]), float(row[2])] for row in coords]


def project_texts_to_3d(texts: list[str]) -> list[list[float]]:
    """Project a list of text snippets into 3D space (no embeddings required)."""

    if not texts:
        return []
    if len(texts) == 1:
        return [[0.0, 0.0, 0.0]]
    if len(texts) == 2:
        return [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]

    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(max_features=2048, stop_words="english")
    mat = vectorizer.fit_transform([t or "" for t in texts])
    if mat.shape[0] < 3 or mat.shape[1] < 2:
        return [[0.0, 0.0, 0.0] for _ in texts]

    max_components = min(3, mat.shape[0] - 1, mat.shape[1] - 1)
    if max_components < 1:
        return [[0.0, 0.0, 0.0] for _ in texts]

    svd = TruncatedSVD(n_components=max_components, random_state=42)
    coords = svd.fit_transform(mat)
    coords = coords - np.mean(coords, axis=0, keepdims=True)

    norms = np.linalg.norm(coords, axis=1)
    max_norm = float(np.max(norms)) if coords.shape[0] else 1.0
    if max_norm > 0:
        coords = coords / max_norm

    if coords.shape[1] < 3:
        pad = np.zeros((coords.shape[0], 3 - coords.shape[1]), dtype=coords.dtype)
        coords = np.concatenate([coords, pad], axis=1)

    return [[float(row[0]), float(row[1]), float(row[2])] for row in coords]


__all__ = [
    "extract_embedding",
    "project_texts_to_3d",
    "project_vectors_to_3d",
    "topic_to_color",
]
