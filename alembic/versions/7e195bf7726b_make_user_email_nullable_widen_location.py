"""make user email nullable, widen location

Revision ID: 7e195bf7726b
Revises: 8c3fb52190cb
Create Date: 2026-08-09 10:43:10.744248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e195bf7726b'
down_revision: Union[str, None] = '8c3fb52190cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.alter_column('location',
               existing_type=sa.VARCHAR(length=5),
               type_=sa.String(length=100),
               existing_nullable=True)

    # Accounts created before user-read-email was requested were stored with an
    # empty email. Because the column is unique, only one such row could ever
    # exist and every later signup failed its insert. Convert them to NULL,
    # which the unique constraint does not treat as a collision.
    op.execute("UPDATE users SET email = NULL WHERE email = ''")


def downgrade() -> None:
    # Restoring NOT NULL requires every row to have a value.
    op.execute("UPDATE users SET email = '' WHERE email IS NULL")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('location',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=5),
               existing_nullable=True)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
