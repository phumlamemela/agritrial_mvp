import base64
import os
import sys
import uuid
from getpass import getpass
from dotenv import load_dotenv
from supabase import create_client
from offline import delete_queued_submission, get_pending_submissions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _insert_returning_id(supabase, table, values, id_column):
    result = supabase.table(table).insert(values).execute()
    if not result.data or id_column not in result.data[0]:
        raise RuntimeError(f"Supabase did not return {id_column} from {table}.")
    return result.data[0][id_column]


def _get_or_create_trial(supabase, payload):
    code = (payload.get("trial_code") or "").strip()
    values = {
        "trial_code": code,
        "trial_name": payload.get("trial_name") or None,
        "target_crop": payload.get("target_crop") or None,
        "objective": payload.get("objective") or None,
        "start_date": payload.get("start_date") or None,
        "end_date": payload.get("end_date") or None,
        "status": payload.get("status") or "Active",
    }
    existing = (
        supabase.table("trial").select("trial_id")
        .eq("trial_code", code).limit(1).execute().data or []
    )
    if existing:
        trial_id = existing[0]["trial_id"]
        updates = {key: value for key, value in values.items() if value not in (None, "")}
        supabase.table("trial").update(updates).eq("trial_id", trial_id).execute()
        return trial_id
    return _insert_returning_id(supabase, "trial", values, "trial_id")


def _get_or_create_site(supabase, trial_id, payload):
    site_name = (payload.get("site_name") or "").strip()
    farm_name = (payload.get("farm_name") or "").strip()
    sites = (
        supabase.table("trial_sites").select("*")
        .eq("trial_id", trial_id).execute().data or []
    )
    for site in sites:
        if ((site.get("site_name") or "").strip().casefold() == site_name.casefold()
                and (site.get("farm_name") or "").strip().casefold() == farm_name.casefold()):
            values = {
                "farmer_name": (payload.get("farmer_name") or "").strip() or None,
                "farm_name": farm_name or None,
                "site_name": site_name,
                "latitude": float(payload["latitude"]) if payload.get("latitude") else None,
                "longitude": float(payload["longitude"]) if payload.get("longitude") else None,
                "soil_type": (payload.get("soil_type") or "").strip() or None,
                "previous_crop": (payload.get("previous_crop") or "").strip() or None,
                "experimental_design": (payload.get("experimental_design") or "").strip() or None,
                "total_replications": int(payload["total_replications"]) if payload.get("total_replications") else None,
            }
            updates = {key: value for key, value in values.items() if value not in (None, "")}
            supabase.table("trial_sites").update(updates).eq("site_id", site["site_id"]).execute()
            return site["site_id"]
    return _insert_returning_id(supabase, "trial_sites", {
        "trial_id": trial_id,
        "farmer_name": payload.get("farmer_name") or None,
        "farm_name": farm_name or None,
        "site_name": site_name,
        "latitude": float(payload["latitude"]) if payload.get("latitude") else None,
        "longitude": float(payload["longitude"]) if payload.get("longitude") else None,
        "soil_type": payload.get("soil_type") or None,
        "previous_crop": payload.get("previous_crop") or None,
        "experimental_design": payload.get("experimental_design") or None,
        "total_replications": int(payload["total_replications"]) if payload.get("total_replications") else None,
    }, "site_id")


def _get_or_create_treatment(supabase, trial_id, payload):
    name = (payload.get("treatment_name") or "").strip()
    treatments = (
        supabase.table("treatment").select("*")
        .eq("trial_id", trial_id).execute().data or []
    )
    rate = (payload.get("application_rate") or "").strip()
    number = (payload.get("treatment_number") or "").strip()
    values = {
        "trial_id": trial_id,
        "treatment_number": int(number) if number else None,
        "treatment_name": name,
        "formulation_details": (payload.get("formulation_details") or "").strip() or None,
        "application_rate": float(rate) if rate else None,
        "rate_unit": (payload.get("rate_unit") or "").strip() or None,
    }
    for treatment in treatments:
        if (treatment.get("treatment_name") or "").strip().casefold() == name.casefold():
            updates = {key: value for key, value in values.items() if value not in (None, "")}
            supabase.table("treatment").update(updates).eq("treatment_id", treatment["treatment_id"]).execute()
            return treatment["treatment_id"]
    return _insert_returning_id(supabase, "treatment", values, "treatment_id")


def save_trait_and_schedule(supabase, trial_id, payload, user_id=None):
    """Persist the capture form's trait definition and assessment dates."""
    trait_name = (payload.get("trait_name") or "").strip()
    trait_id = None
    if trait_name:
        traits = supabase.table("assessment_traits").select("*").eq("trial_id", trial_id).execute().data or []
        trait = next((row for row in traits
                      if (row.get("trait_name") or "").strip().casefold() == trait_name.casefold()), None)
        trait_values = {
            "trial_id": trial_id,
            "trait_name": trait_name,
            "unit_of_measure": (payload.get("trait_unit") or "").strip() or None,
            "methodology": (payload.get("trait_description") or "").strip() or None,
            "data_type": "numeric",
        }
        if trait:
            trait_id = trait["trait_id"]
            updates = {key: value for key, value in trait_values.items() if value not in (None, "")}
            supabase.table("assessment_traits").update(updates).eq("trait_id", trait_id).execute()
        else:
            result = supabase.table("assessment_traits").insert(trait_values).execute()
            if not result.data or "trait_id" not in result.data[0]:
                raise RuntimeError("Supabase did not return trait_id from assessment_traits.")
            trait_id = result.data[0]["trait_id"]

    stage = (payload.get("assessment_stage") or "").strip() or None
    scheduled_date = (payload.get("scheduled_date") or "").strip() or None
    completed_date = (payload.get("completed_date") or "").strip() or None
    if stage or scheduled_date or completed_date:
        schedules = supabase.table("assessment_schedule").select("*").eq("trial_id", trial_id).execute().data or []
        matching = next((row for row in schedules
                         if row.get("trait_id") == trait_id
                         and (row.get("assessment_stage") or None) == stage
                         and (row.get("scheduled_date") or None) == scheduled_date), None)
        schedule_values = {
            "trial_id": trial_id,
            "trait_id": trait_id,
            "assessment_stage": stage,
            "scheduled_date": scheduled_date,
            "completed_date": completed_date,
            "created_by": user_id,
        }
        if matching:
            updates = {key: value for key, value in schedule_values.items() if value not in (None, "")}
            supabase.table("assessment_schedule").update(updates).eq("schedule_id", matching["schedule_id"]).execute()
        else:
            supabase.table("assessment_schedule").insert(schedule_values).execute()
    return trait_id


def upload_submission_photo(supabase, payload, trial_id, site_id, treatment_id, plot_id, user_id):
    """Upload a queued or online capture photo and save its private Storage path."""
    encoded = payload.get("_photo_base64")
    if not encoded:
        return None
    content_type = (payload.get("_photo_content_type") or "").lower()
    extensions = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "image/heic": ".heic", "image/heif": ".heif",
    }
    if content_type not in extensions:
        raise ValueError("Unsupported photo type.")
    photo_bytes = base64.b64decode(encoded, validate=True)
    if not photo_bytes or len(photo_bytes) > 8 * 1024 * 1024:
        raise ValueError("Photo must be between 1 byte and 8 MB.")
    try:
        photo_key = str(uuid.UUID(payload.get("_photo_key", "")))
    except (ValueError, TypeError, AttributeError):
        photo_key = str(uuid.uuid4())
    storage_path = f"{user_id}/{trial_id}/{photo_key}{extensions[content_type]}"
    supabase.storage.from_("trial-photos").upload(
        storage_path,
        photo_bytes,
        file_options={"content-type": content_type, "cache-control": "3600", "upsert": "true"},
    )
    photo_row = {
        "photo_key": photo_key,
        "trial_id": trial_id,
        "site_id": site_id,
        "treatment_id": treatment_id,
        "plot_id": plot_id,
        "storage_path": storage_path,
        "file_name": (payload.get("_photo_filename") or "trial-photo")[:255],
        "content_type": content_type,
        "captured_by": user_id,
    }
    supabase.table("trial_photos").upsert(photo_row, on_conflict="photo_key").execute()
    return storage_path


def _sync_one_submission(supabase, payload, owner_user_id=None):
    trial_id = _get_or_create_trial(supabase, payload)
    site_id = _get_or_create_site(supabase, trial_id, payload)
    treatment_id = _get_or_create_treatment(supabase, trial_id, payload)
    year = int(payload.get("year") or 2026)
    replicate = int(payload.get("replicate") or payload.get("replication_number") or 1)
    plot_number = int(payload.get("plot_number") or 1)
    plots = (
        supabase.table("plots").select("*")
        .eq("site_id", site_id)
        .eq("treatment_id", treatment_id)
        .eq("plot_number", plot_number)
        .eq("replication_number", replicate)
        .limit(1).execute().data or []
    )
    if plots:
        plot_id = plots[0]["plot_id"]
        plot_updates = {
            key: int(payload[key]) for key in ("row_index", "column_index") if payload.get(key)
        }
        if plot_updates:
            supabase.table("plots").update(plot_updates).eq("plot_id", plot_id).execute()
    else:
        plot_id = _insert_returning_id(supabase, "plots", {
            "site_id": site_id,
            "treatment_id": treatment_id,
            "plot_number": plot_number,
            "replication_number": replicate,
            "row_index": int(payload["row_index"]) if payload.get("row_index") else None,
            "column_index": int(payload["column_index"]) if payload.get("column_index") else None,
        }, "plot_id")

    save_trait_and_schedule(supabase, trial_id, payload, owner_user_id)

    metric_fields = {
        "yield_value": payload.get("yield_value"),
        "bio_yield": payload.get("bio_yield"),
        "pod_per_plant": payload.get("pods_per_plant"),
    }
    if any(value not in (None, "") for value in metric_fields.values()) or payload.get("measurement_date"):
        measurement = {"treatment_id": treatment_id, "year": year, "replicate": replicate}
        for field, value in metric_fields.items():
            if value not in (None, ""):
                measurement[field] = float(value)
        if payload.get("measurement_date"):
            measurement["measurement_date"] = payload["measurement_date"]
        supabase.table("measurement").upsert(
            measurement, on_conflict="treatment_id,year,replicate"
        ).execute()

    if payload.get("_photo_base64"):
        upload_submission_photo(
            supabase, payload, trial_id, site_id, treatment_id, plot_id, owner_user_id
        )


def sync_pending_submissions(supabase, owner_user_id):
    pending = get_pending_submissions(owner_user_id)
    synced = 0
    for item in pending:
        _sync_one_submission(supabase, item["payload"], owner_user_id)
        delete_queued_submission(item["queue_id"])
        synced += 1
    return synced


def main():
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY in .env first.")
    email = input("Supabase account email: ").strip()
    password = getpass("Supabase account password: ")
    supabase = create_client(url, key)
    auth = supabase.auth.sign_in_with_password({"email": email, "password": password})
    metadata = getattr(auth.user, "user_metadata", None) or {}
    app_metadata = getattr(auth.user, "app_metadata", None) or {}
    role = str(metadata.get("requested_role") or metadata.get("role") or app_metadata.get("role") or "").strip().lower()
    if role != "farmer":
        raise PermissionError("Only a farmer account can sync farmer submissions.")
    count = sync_pending_submissions(supabase, auth.user.id)
    print(f"Sync complete: {count} queued submission(s) uploaded.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Sync failed; unsynced entries were kept: {error}", file=sys.stderr)
        raise SystemExit(1)
