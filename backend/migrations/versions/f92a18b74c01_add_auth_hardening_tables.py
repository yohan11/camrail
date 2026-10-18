"""add auth hardening tables refresh_tokens revoked_tokens login_attempts

Revision ID: f92a18b74c01
Revises: e41d8f72a912
Create Date: 2026-10-18 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f92a18b74c01'
down_revision = 'e41d8f72a912'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Table refresh_tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('replaced_by', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('ip', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)

    # 2. Table revoked_tokens
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_revoked_tokens_jti'), 'revoked_tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_revoked_tokens_expires_at'), 'revoked_tokens', ['expires_at'], unique=False)

    # 3. Table login_attempts
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email_lower', sa.String(length=255), nullable=False),
        sa.Column('ip', sa.String(length=100), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('success', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_attempts_email_lower'), 'login_attempts', ['email_lower'], unique=False)
    op.create_index(op.f('ix_login_attempts_ip'), 'login_attempts', ['ip'], unique=False)
    op.create_index(op.f('ix_login_attempts_attempted_at'), 'login_attempts', ['attempted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_login_attempts_attempted_at'), table_name='login_attempts')
    op.drop_index(op.f('ix_login_attempts_ip'), table_name='login_attempts')
    op.drop_index(op.f('ix_login_attempts_email_lower'), table_name='login_attempts')
    op.drop_table('login_attempts')

    op.drop_index(op.f('ix_revoked_tokens_expires_at'), table_name='revoked_tokens')
    op.drop_index(op.f('ix_revoked_tokens_jti'), table_name='revoked_tokens')
    op.drop_table('revoked_tokens')

    op.drop_index(op.f('ix_refresh_tokens_expires_at'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
