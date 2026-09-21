"""
Qdrant vector store wrapper: collection setup, upser, RBAC-filtered query.
"""

import uuid 
from qdrant_client import QdrantClient
from qdrant_client.models import(
    Distance,
    FieldCondition, 
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

_EMBEDDING_DIM = 384 # BAAI/bge-small-en-v1.5 ouput dimension

_client: QdrantClient |None = None


# Creates (or reuses) a single shared Qdrant connection

def get_client() -> QdrantClient:
    global _client 
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key= settings.qdrant_api_key)
    return _client
    
# Creates the collection if it doesn't already exist
def ensure_collection() -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name = settings.qdrant_collection,
            vectors_config=VectorParams(size= _EMBEDDING_DIM, distance= Distance.COSINE),    
        )
# Delete old chunks for a file before re-ingesting it
def delete_by_source_file(source_file: str) -> None:
    client = get_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
        ),
    )
# Stores chunk vectors and metadata into the collection

def upsert_chunks(chunks: list[dict]) -> None:
    client = get_client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()), 
            vector=c["embedding"],
            payload={
                "text": c["text"], 
                "department": c["department"], 
                "access_level": c["access_level"], 
                "source_file": c["source_file"],
                "page": c["page"],
            },
        )
        for c in chunks
    ]
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=points
    )

# Searches for similar chunks, filtered by RBAC rules at the DB layer,

def query(embedding: list[float],rbac_filter: Filter, k: int = 5) -> list[dict]:
    
    client = get_client()
    results = client.query_points(
        collection_name = settings.qdrant_collection,
        query = embedding, 
        query_filter=rbac_filter,
        limit=k,
        with_payload=True,

    )

    return [
        {
            "text": p.payload["text"],
            "department": p.payload["department"],
            "access_level": p.payload["access_level"],
            "source_file": p.payload["source_file"],
            "page": p.payload["page"],
            "score": p.score,
        }
        for p in results.points
    ]