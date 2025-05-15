"""Create reply_log table

Revision ID: 52dd1368b33b
Revises: 0918ec896c35
Create Date: 2025-05-15 12:22:17.404799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52dd1368b33b'
down_revision: Union[str, None] = '0918ec896c35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'reply_log',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        # VARCHAR(50) 대신 BigInteger 사용
        sa.Column('post_tweet_id', sa.BigInteger, nullable=False),
        sa.Column('reply_text', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ['post_tweet_id'],
            ['post.tweet_id'],
            name='reply_log_ibfk_1'
        ),
    )
    op.create_index('ix_reply_log_post_tweet_id', 'reply_log', ['post_tweet_id'])


def downgrade() -> None:
    """Downgrade schema."""
    pass
