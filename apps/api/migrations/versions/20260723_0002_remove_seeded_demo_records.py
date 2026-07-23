"""Remove the legacy seeded CareRelay accounts and their linked records."""

from alembic import op


revision = "20260723_0002"
down_revision = "20260721_0001"
branch_labels = None
depends_on = None


SEEDED_EMAILS = """
    'patient@demo.carerelay.local',
    'clinician@demo.carerelay.local',
    'reviewer@demo.carerelay.local',
    'admin@demo.carerelay.local'
"""


def upgrade() -> None:
    seeded_user_ids = f"SELECT id FROM users WHERE email IN ({SEEDED_EMAILS})"
    seeded_encounter_ids = f"SELECT id FROM encounters WHERE patient_id IN ({seeded_user_ids})"
    op.execute(
        f"DELETE FROM audit_events WHERE actor_id IN ({seeded_user_ids}) "
        f"OR encounter_id IN ({seeded_encounter_ids})"
    )
    op.execute(f"DELETE FROM escalations WHERE encounter_id IN ({seeded_encounter_ids})")
    op.execute(f"DELETE FROM encounters WHERE patient_id IN ({seeded_user_ids})")
    op.execute(f"DELETE FROM users WHERE id IN ({seeded_user_ids})")


def downgrade() -> None:
    # Deleted synthetic records are intentionally not recreated.
    pass
