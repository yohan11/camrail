"""add hnsw and gin indexes to document_chunks

Revision ID: e41d8f72a912
Revises: 6a72c013cc75
Create Date: 2026-10-14 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e41d8f72a912'
down_revision = '6a72c013cc75'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Vérifier et assurer la présence de l'extension pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Création idempotente de l'index HNSW sur DocumentChunk.embedding
    # Paramètres haute performance : vector_cosine_ops, m=16, ef_construction=64
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 3. Création idempotente de l'index GIN sur DocumentChunk.search_vector
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_search_vector
        ON document_chunks USING GIN (search_vector);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector;")
