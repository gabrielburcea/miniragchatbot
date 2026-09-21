"""Builds the RBAC filter and retrieves chunks for a given user.
Retrieval layer that enforces RBAC before results ever reach the LLM.

Rule (from README): department == user.department AND access_level <= user.level,
with one exception — hr content is visible to any authenticated user regardless
of their own department. This filter is applied inside Qdrant itself (query_filter),
not by fetching everything and discarding rows in Python, so unauthorised chunks
never leave the database.

"""

from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from app.rag.vectorstore import query
from app.rag.embeddings import embed_query


def build_rbac_filter(department: str, level: int) -> Filter:
    """Own-department chunks OR hr chunks, both capped by user level."""

    # Group 1: chunks belonging to the user's own department, at or below their level
    own_dept_group = Filter(
        must=[
            FieldCondition(key="department", match=MatchValue(value=department)),
            FieldCondition(key="access_level", range=Range(lte=level)),
        ]
    )

    # Group 2: hr chunks are visible to everyone, regardless of their own department
    hr_group = Filter(
        must=[
            FieldCondition(key="department", match=MatchValue(value="hr")),
            FieldCondition(key="access_level", range=Range(lte=level)),
        ]
    )

    # A chunk matches if EITHER group matches (OR, not AND) - satisfies the README exception
    return Filter(should=[own_dept_group, hr_group])


def retrieve_chunks(question: str, department: str, level: int, top_k: int = 5):
    """Embeds the question and queries Qdrant with the RBAC filter applied."""

    # Turn the user's question into the same vector space as the stored chunks
    query_vector = embed_query(question)

    # Build the department + level filter enforced at the Qdrant query layer, not in Python
    rbac_filter = build_rbac_filter(department, level)

    # Vector similarity search, restricted server-side to only authorised chunks
    return query(query_vector, rbac_filter, top_k)