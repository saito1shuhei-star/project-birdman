"""migrate category values to glider human_powered_propeller

Revision ID: 9706411a806d
Revises: aedebbdef4cb
Create Date: 2026-07-19 08:50:02.928683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9706411a806d'
down_revision: Union[str, Sequence[str], None] = 'aedebbdef4cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate legacy category values to the corrected enum.

    Category enum was corrected per the official 2025 rulebook
    (glider / human_powered_propeller / other). Legacy values:
    - 'distance'   -> 'human_powered_propeller' (old default; PBM targets the
                       human-powered propeller division first)
    - 'time_trial' -> 'other' (no direct equivalent in the official divisions)
    """
    op.execute(
        "UPDATE projects SET category = 'human_powered_propeller' "
        "WHERE category = 'distance'"
    )
    op.execute("UPDATE projects SET category = 'other' WHERE category = 'time_trial'")


def downgrade() -> None:
    """Downgrade schema.

    Irreversible data migration: the legacy distinction cannot be restored
    exactly. Map back to the closest legacy value.
    """
    op.execute(
        "UPDATE projects SET category = 'distance' "
        "WHERE category IN ('human_powered_propeller', 'glider')"
    )
