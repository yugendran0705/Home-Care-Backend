"""
populate_nurses.py

Seeds 10 nurse accounts by calling NurseService.create_nurse_and_user_account
directly against the DB (no HTTP layer involved), then for each nurse:
  1. Randomly assigns 1-3 *active* service IDs (never empty).
  2. Picks one random schedule template from working_hours_seed.json and
     creates it via WorkingHoursService.bulk_create_working_hours.
  3. Picks 0-2 random blackout templates from blackout_dates_seed.json,
     converts their relative offsets into real future datetimes, and
     creates them via BlackoutDateService.create_blackout_date.

All of this uses the nurse's own DB-generated id, so it happens right after
each nurse is created rather than as a separate pass.

--------------------------------------------------------------------------
ASSUMPTIONS (adjust these imports if your project layout differs):
    1. DB session factory     -> config.database.SessionLocal
    2. Nurse input schema     -> schemas.nurses.NurseCreate
    3. Working hours schema   -> schemas.working_hours.WorkingHoursCreate
       fields: day_of_week (int 0-6), start_time, end_time
    4. Blackout date schema   -> schemas.blackout_dates.BlackoutDateCreate
       fields: start_datetime, end_datetime, reason
    5. Working hours service  -> services.working_hours.WorkingHoursService
    6. Blackout date service  -> services.blackout_dates.BlackoutDateService
Everything else is inferred from services/nurses.py, services/nursing_services.py,
services/working_hours.py and services/blackout_dates.py as shown in your editor.
--------------------------------------------------------------------------

Run from the project root (Home-Care-Backend/) with your venv active:
    python populate_nurses.py
"""

import json
import random
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

from fastapi import HTTPException

# --- ASSUMPTION 1 -----------------------------------------------------------
from config.database import SessionLocal

# --- ASSUMPTIONS 2-4 ---------------------------------------------------------
from schemas.nurses import NurseCreate
from schemas.working_hours import WorkingHoursCreate
from schemas.blackout_dates import BlackoutDateCreate

# --- ASSUMPTIONS 5-6, plus the services already used before ------------------
from services.nurses import NurseService
from services.nursing_services import NursingServiceService
from services.working_hours import WorkingHoursService
from services.blackout_dates import BlackoutDateService

SEED_FILE = Path(__file__).parent / "nurses_seed.json"
WORKING_HOURS_SEED_FILE = Path(__file__).parent / "working_hours_seed.json"
BLACKOUT_DATES_SEED_FILE = Path(__file__).parent / "blackout_dates_seed.json"

MIN_SERVICES_PER_NURSE = 1
MAX_SERVICES_PER_NURSE = 3
MAX_BLACKOUTS_PER_NURSE = 2


def load_json(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seed_nurses() -> list[dict]:
    return load_json(SEED_FILE)


def get_active_service_ids(db) -> list[str]:
    """Fetch all services and keep only the active ones' IDs."""
    service_service = NursingServiceService(db)
    all_services = service_service.list_all_services(skip=0, limit=1000)
    active_ids = [str(s.id) for s in all_services if getattr(s, "is_active", True)]
    return active_ids


def assign_random_services(nurse_dict: dict, active_service_ids: list[str]) -> dict:
    """Attach a non-empty, random, de-duplicated set of service_ids to a nurse."""
    count = random.randint(
        MIN_SERVICES_PER_NURSE, min(MAX_SERVICES_PER_NURSE, len(active_service_ids))
    )
    chosen_ids = random.sample(active_service_ids, count)
    nurse_dict["services"] = [{"service_ids": chosen_ids}]
    return nurse_dict


def extract_nurse_id(create_result):
    """
    NurseCreateResponse's exact shape wasn't visible, so try the common
    possibilities in order: a top-level .id, a nested .nurse.id, or .nurse_id.
    """
    for attr_path in (("id",), ("nurse", "id"), ("nurse_id",)):
        obj = create_result
        for attr in attr_path:
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        if obj is not None:
            return obj
    return None


def generate_working_hours(templates: list[dict]) -> list:
    """Pick one random schedule template from the JSON pool for this nurse."""
    template = random.choice(templates)
    return [
        WorkingHoursCreate(
            day_of_week=slot["day_of_week"],
            start_time=time.fromisoformat(slot["start_time"]),
            end_time=time.fromisoformat(slot["end_time"]),
        )
        for slot in template["slots"]
    ]


def generate_blackout_dates(templates: list[dict], stagger_index: int) -> list:
    """
    Pick 0-2 random blackout templates from the JSON pool and convert their
    relative offsets into real future datetimes for this nurse.

    stagger_index spaces each nurse's windows further into the future so a
    nurse never ends up with two overlapping picks even if random.sample
    happens to choose adjacent-offset templates.
    """
    num_blackouts = random.randint(0, min(MAX_BLACKOUTS_PER_NURSE, len(templates)))
    chosen_templates = random.sample(templates, k=num_blackouts)
    blackouts = []

    for i, tmpl in enumerate(chosen_templates):
        start = datetime.utcnow() + timedelta(
            days=tmpl["start_offset_days"] + stagger_index * 10 + i * 14
        )
        end = start + timedelta(days=tmpl["duration_days"])
        blackouts.append(
            BlackoutDateCreate(start_datetime=start, end_datetime=end, reason=tmpl["reason"])
        )
    return blackouts


def main():
    seed_nurses = load_seed_nurses()
    working_hours_templates = load_json(WORKING_HOURS_SEED_FILE)
    blackout_date_templates = load_json(BLACKOUT_DATES_SEED_FILE)

    db = SessionLocal()
    created, failed = [], []

    try:
        active_service_ids = get_active_service_ids(db)
        if not active_service_ids:
            print(
                "No active services found in the DB. "
                "Seed your nursing services first, then re-run this script."
            )
            sys.exit(1)

        print(f"Found {len(active_service_ids)} active service(s) to assign from.\n")

        nurse_service = NurseService(db)
        working_hours_service = WorkingHoursService(db)
        blackout_date_service = BlackoutDateService(db)

        for i, nurse_dict in enumerate(seed_nurses, start=1):
            nurse_dict = assign_random_services(dict(nurse_dict), active_service_ids)

            # --- Step 1: create the nurse ---------------------------------
            try:
                nurse_in = NurseCreate(**nurse_dict)
                result = nurse_service.create_nurse_and_user_account(nurse_in=nurse_in)
                db.commit()
                created.append((nurse_dict["email"], nurse_dict["services"]))
                print(
                    f"[{i:02}] Created nurse: {nurse_dict['first_name']} "
                    f"{nurse_dict['last_name']} ({nurse_dict['email']}) "
                    f"-> services: {nurse_dict['services'][0]['service_ids']}"
                )
            except HTTPException as e:
                db.rollback()
                failed.append((nurse_dict["email"], f"nurse creation: {e.detail}"))
                print(f"[{i:02}] FAILED (nurse creation): {nurse_dict['email']} -> {e.detail}")
                continue
            except Exception as e:
                db.rollback()
                failed.append((nurse_dict["email"], f"nurse creation: {e}"))
                print(f"[{i:02}] FAILED (nurse creation): {nurse_dict['email']} -> {e}")
                continue

            nurse_id = extract_nurse_id(result)
            if nurse_id is None:
                print(
                    f"     -> Could not determine nurse_id from the response; "
                    f"skipping working hours / blackout dates for this nurse. "
                    f"Check extract_nurse_id() against your actual NurseCreateResponse shape."
                )
                continue

            # --- Step 2: working hours -------------------------------------
            try:
                wh_data = generate_working_hours(working_hours_templates)
                working_hours_service.bulk_create_working_hours(
                    nurse_id=nurse_id, working_hours_data=wh_data
                )
                db.commit()
                days = sorted(wh.day_of_week for wh in wh_data)
                print(f"     -> working hours created for day(s): {days}")
            except HTTPException as e:
                db.rollback()
                print(f"     -> working hours FAILED: {e.detail}")
            except Exception as e:
                db.rollback()
                print(f"     -> working hours FAILED: {e}")

            # --- Step 3: blackout dates --------------------------------------
            try:
                blackout_list = generate_blackout_dates(blackout_date_templates, i)
                for blackout in blackout_list:
                    blackout_date_service.create_blackout_date(
                        nurse_id=nurse_id, blackout_data=blackout
                    )
                db.commit()
                if blackout_list:
                    print(f"     -> {len(blackout_list)} blackout date(s) created")
            except HTTPException as e:
                db.rollback()
                print(f"     -> blackout dates FAILED: {e.detail}")
            except Exception as e:
                db.rollback()
                print(f"     -> blackout dates FAILED: {e}")

    finally:
        db.close()

    print("\n--- Summary ---")
    print(f"Created: {len(created)} / {len(seed_nurses)}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for email, reason in failed:
            print(f"  - {email}: {reason}")


if __name__ == "__main__":
    main()
