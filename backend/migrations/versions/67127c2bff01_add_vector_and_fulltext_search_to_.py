"""add vector and fulltext search to document_chunks

Revision ID: 67127c2bff01
Revises: b153c6d165c2
Create Date: 2026-08-08 23:18:49.874996

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision = '67127c2bff01'
down_revision = 'b153c6d165c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure vector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Add search_vector and update embedding column
    op.add_column('document_chunks', sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384);")

    # Create GIN index on search_vector for full-text search
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_chunks_search_vector ON document_chunks USING GIN(search_vector);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector;")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE text USING embedding::text;")
    op.drop_column('document_chunks', 'search_vector')
