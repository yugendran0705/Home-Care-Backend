"""
populate_db.py

Seeds the nursing_services table from nursing_services.json.

Place this file at the project root (same level as main.py, services/, schemas/, repositories/)
and run it with:

    python populate_db.py

Before running:
- Fix the SessionLocal import below to match wherever your DB session factory
  actually lives (e.g. config.database, config.db, database, etc). Check how
  get_db() is defined/imported in your dependencies.py or main.py and copy
  that import.
- Make sure nursing_services.json sits next to this script (or update DATA_FILE).
"""

import json
from pathlib import Path

from config.database import SessionLocal  # <-- adjust to your actual module
from schemas.nursing_services import NursingServiceCreate
from services.nursing_services import NursingServiceService

DATA_FILE = Path(__file__).parent / "nursing_services.json"


def load_services(file_path: Path) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def populate_services() -> None:
    db = SessionLocal()
    service = NursingServiceService(db)

    services_data = load_services(DATA_FILE)

    created_count = 0
    skipped_count = 0

    for entry in services_data:
        try:
            service_in = NursingServiceCreate(**entry)
            service.create_service(service_in=service_in)
            created_count += 1
            print(f"Created: {entry['service_name']}")
        except Exception as e:
            # create_service raises HTTPException on duplicate names,
            # and the service layer already rolls back on DB errors.
            skipped_count += 1
            print(f"Skipped '{entry.get('service_name')}': {e}")

    db.close()
    print(f"\nDone. Created: {created_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    populate_services()
