from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from alfred_app.core.config import settings
import hashlib, math

client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

def ensure_collection(dim: int = 128):
    cols = client.get_collections().collections
    names = [c.name for c in cols]
    if settings.qdrant_collection not in names:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

def fake_embed(text: str, dim: int = 128) -> list[float]:
    # Cheap deterministic embedding for tonight; replace with real model later.
    h = hashlib.sha256(text.encode()).digest()
    vec = [(h[i % len(h)]/255.0 - 0.5) for i in range(dim)]
    n = math.sqrt(sum(v*v for v in vec)) or 1.0
    return [v/n for v in vec]

def upsert_text(doc_id: str, text: str, meta: dict | None = None):
    ensure_collection()
    pid = int(hashlib.md5(doc_id.encode()).hexdigest()[:12], 16)
    vec = fake_embed(text)
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[PointStruct(id=pid, vector=vec, payload={"meta": meta or {}, "text": text})]
    )
