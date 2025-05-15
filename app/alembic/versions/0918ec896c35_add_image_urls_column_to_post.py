"""Add image_urls column to post

Revision ID: 0918ec896c35
Revises: 
Create Date: 2025-05-15 12:16:50.670624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0918ec896c35'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'post',
        sa.Column(
            'image_urls',
            sa.JSON(),
            nullable=True,
            comment='트윗 이미지 URL 목록(JSON 배열)'
        )
    )


def downgrade() -> None:
    ""
