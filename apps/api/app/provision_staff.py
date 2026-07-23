"""Provision the four demo login accounts (patient / clinician / reviewer / admin)."""

from __future__ import annotations

import logging
import os
import sys

from .database import initialize_database
from .schemas import Role
from .store import Store

logger = logging.getLogger(__name__)

# Familiar hackathon credentials (same as the original seeded accounts).
DEMO_USERS = [
    (Role.PATIENT, "patient@demo.carerelay.local", "Maya Patient", "demo-patient"),
    (Role.CLINICIAN, "clinician@demo.carerelay.local", "Dr. Ellis", "demo-clinician"),
    (Role.REVIEWER, "reviewer@demo.carerelay.local", "Jordan Reviewer", "demo-reviewer"),
    (Role.ADMIN, "admin@demo.carerelay.local", "Avery Admin", "demo-admin"),
]


def provision_demo_users(store: Store | None = None) -> dict[str, list[str]]:
    target = store or Store()
    created: list[str] = []
    existing: list[str] = []

    for role, email, name, default_password in DEMO_USERS:
        env_key = f"DEMO_{role.value.upper()}_PASSWORD"
        password = os.getenv(env_key, default_password)
        try:
            target.create_user(email=email, password=password, name=name, role=role)
            created.append(f"{role.value}: {email}")
            logger.info("provisioned %s account %s", role.value, email)
        except ValueError as exc:
            if str(exc) != "EMAIL_TAKEN":
                raise
            existing.append(f"{role.value}: {email}")

    return {"created": created, "existing": existing}


def main() -> int:
    initialize_database()
    result = provision_demo_users()
    print("Demo account provisioning complete.")
    if result["created"]:
        print("Created:")
        for line in result["created"]:
            print(f"  - {line}")
    if result["existing"]:
        print("Already present:")
        for line in result["existing"]:
            print(f"  - {line}")
    print(
        "\nLogin accounts:\n"
        "  patient@demo.carerelay.local / demo-patient\n"
        "  clinician@demo.carerelay.local / demo-clinician\n"
        "  reviewer@demo.carerelay.local / demo-reviewer\n"
        "  admin@demo.carerelay.local / demo-admin"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
