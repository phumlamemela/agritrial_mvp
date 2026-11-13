import base64
import csv
import io
import os
import secrets
import httpx
import time
import uuid
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from supabase import create_client
from werkzeug.utils import secure_filename
from ci_calculator1 import calculate_confidence_intervals
from chart import generate_researcher_charts, generate_yield_chart

from offline import authenticate_cached_login, cache_offline_login, pending_submission_count, save_submission_offline
from sync_SupaBASE import save_trait_and_schedule, sync_pending_submissions, upload_submission_photo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 9 * 1024 * 1024
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key and os.getenv("APP_ENV", "development").lower() == "production":
    raise RuntimeError("Set a strong FLASK_SECRET_KEY in the production environment.")
app.secret_key = secret_key or secrets.token_hex(32)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY in the .env file.")
supabase = create_client(supabase_url, supabase_key)

ROLE_ENDPOINTS = {
    "capture": {"farmer"},
    "farmer_dashboard": {"farmer"},
    "submit": {"farmer"},
    "sync_data": {"farmer"},
    "researcher_dashboard": {"researcher", "uwc", "su_arise"},
    "download_researcher_csv": {"researcher", "uwc", "su_arise"},
    "confidence_interval": {"farmer", "researcher", "uwc", "su_arise"},
    "dalrrd_dashboard": {"dalrrd"},
    "verify_trial": {"dalrrd"},
    "query_trial": {"dalrrd"},
    "download_dalrrd_report": {"dalrrd"},
    "investor_dashboard": {"investor", "funder"},
    "partner_dashboard": {"partner"},
}


@app.before_request
def enforce_role_access():
    allowed_roles = ROLE_ENDPOINTS.get(request.endpoint)
    if allowed_roles is None:
        return None
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") not in allowed_roles:
        abort(403)
    return None


def _insert_one(table, values, id_column):
    response = supabase.table(table).insert(values).execute()
    if not response.data or id_column not in response.data[0]:
        raise RuntimeError(f"Supabase did not return {id_column} for {table}.")
    return response.data[0][id_column]


def _nonblank_fields(values):
    """Keep submitted values, including numeric zero, but leave blank fields unchanged."""
    return {key: value for key, value in values.items() if value not in (None, "")}


def measurements_and_ci():
    measurements = supabase.table("measurement").select("*").execute().data or []
    treatments = (
        supabase.table("treatment")
        .select("treatment_id,trial_id,treatment_name")
        .execute()
        .data or []
    )
    trials = (
        supabase.table("trial")
        .select("trial_id,trial_code")
        .execute()
        .data or []
    )
    intervals = calculate_confidence_intervals(
        measurements=measurements,
        treatments=treatments,
        trials=trials,
        metric="yield_value",
        confidence=0.95,
    )
    return measurements, intervals


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session.clear()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user = response.user
            user_metadata = getattr(user, "user_metadata", None) or {}
            app_metadata = getattr(user, "app_metadata", None) or {}
            requested_role = str(user_metadata.get("requested_role") or user_metadata.get("role") or "").strip().lower()
            approved_role = str(app_metadata.get("role") or "").strip().lower()
            known_roles = {"farmer", "researcher", "uwc", "su_arise", "investor", "funder", "partner", "dalrrd"}
            role = requested_role if requested_role in known_roles else approved_role
            if role not in known_roles:
                return "Your account has no role saved. Please register again and choose a role.", 403
            if role == "farmer":
                try:
                    cache_offline_login(user.id, email, role, password)
                except Exception:
                    app.logger.exception("Could not cache offline farmer login")
            session["user_id"] = user.id
            session["email"] = email.strip().casefold()
            session["role"] = role
            session["offline"] = False
            dashboard_endpoints = {
                "farmer": "capture", "researcher": "researcher_dashboard",
                "uwc": "researcher_dashboard", "su_arise": "researcher_dashboard",
                "investor": "investor_dashboard", "funder": "investor_dashboard",
                "partner": "partner_dashboard", "dalrrd": "dalrrd_dashboard",
            }
            return redirect(url_for(dashboard_endpoints[role]))
        except (httpx.NetworkError, httpx.TimeoutException):
            cached = authenticate_cached_login(email, password)
            if cached and cached["role"] == "farmer":
                session["user_id"] = cached["user_id"]
                session["email"] = cached["email"]
                session["role"] = "farmer"
                session["offline"] = True
                flash("Signed in using this device's saved farmer access. New entries will be stored locally until sync.", "warning")
                return redirect(url_for("capture"))
            return "No internet connection. This device needs one successful online farmer sign-in before offline login will work.", 503
        except Exception:
            app.logger.exception("Login failed")
            return "Login failed. Check your email and password.", 401

    return render_template("login.html")

@app.route("/capture", methods=["GET"])
def capture():
    return render_template("index.html", pending_count=pending_submission_count(session["user_id"]))


@app.route("/home")
def home():
    return redirect(url_for("login"))


@app.route("/farmer-dashboard")
def farmer_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("offline"):
        return redirect(url_for("capture"))

    measurements, ci_results = measurements_and_ci()
    chart_path = os.path.join(app.static_folder, "farmer_yield_chart.png")
    generate_yield_chart(ci_results, chart_path)

    return render_template(
        "Farmerdashboard.html",
        measurements=measurements,
        ci_results=ci_results,
        chart_version=int(time.time()),
        updated=request.args.get("updated") == "1",
    )


@app.route("/researcher-dashboard")
def researcher_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    trials = supabase.table("trial").select("*").execute().data or []
    treatments = (
        supabase.table("treatment")
        .select("treatment_id,trial_id,treatment_name")
        .execute()
        .data or []
    )
    all_measurements = supabase.table("measurement").select("*").execute().data or []
    assessments = supabase.table("assessment_data").select("*").execute().data or []

    trial_code_by_id = {
        str(trial.get("trial_id")): (trial.get("trial_code") or "")
        for trial in trials
    }
    treatment_by_id = {
        str(treatment.get("treatment_id")): treatment
        for treatment in treatments
    }
    trial_codes = sorted({
        code for code in trial_code_by_id.values() if code
    })
    selected_trial = request.args.get("trial_code", "").strip()
    if selected_trial not in trial_codes:
        selected_trial = ""

    if selected_trial:
        measurements = []
        for row in all_measurements:
            treatment = treatment_by_id.get(str(row.get("treatment_id")))
            if treatment and trial_code_by_id.get(str(treatment.get("trial_id"))) == selected_trial:
                measurements.append(row)
    else:
        measurements = all_measurements

    chart_version = int(time.time())
    boxplot_path = os.path.join(app.static_folder, "researcher_yield_boxplot.png")
    heatmap_path = os.path.join(app.static_folder, "researcher_correlation_heatmap.png")
    generate_researcher_charts(
        measurements=all_measurements,
        treatments=treatments,
        trials=trials,
        selected_trial_code=selected_trial,
        boxplot_path=boxplot_path,
        heatmap_path=heatmap_path,
    )

    return render_template(
        "Researcherdashboard.html",
        trials=trials,
        measurements=measurements,
        assessments=assessments,
        trial_codes=trial_codes,
        selected_trial=selected_trial,
        chart_version=chart_version,
    )


@app.route("/download-researcher-csv")
def download_researcher_csv():
    if "user_id" not in session:
        return redirect(url_for("login"))

    trials = supabase.table("trial").select("trial_id,trial_code").execute().data or []
    treatments = (
        supabase.table("treatment")
        .select("treatment_id,trial_id,treatment_name")
        .execute()
        .data or []
    )
    measurements = supabase.table("measurement").select("*").execute().data or []

    trial_code_by_id = {
        str(trial.get("trial_id")): (trial.get("trial_code") or "")
        for trial in trials
    }
    treatment_by_id = {
        str(treatment.get("treatment_id")): treatment
        for treatment in treatments
    }
    valid_trial_codes = set(trial_code_by_id.values())
    selected_trial = request.args.get("trial_code", "").strip()
    if selected_trial not in valid_trial_codes:
        selected_trial = ""
    search = request.args.get("search", "").strip().casefold()

    if selected_trial:
        measurements = [
            row for row in measurements
            if (treatment := treatment_by_id.get(str(row.get("treatment_id"))))
            and trial_code_by_id.get(str(treatment.get("trial_id"))) == selected_trial
        ]
    if search:
        measurements = [
            row for row in measurements
            if search in " ".join(str(value) if value is not None else "" for value in row.values()).casefold()
        ]

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    headers = list(measurements[0].keys()) if measurements else [
        "measurement_id", "treatment_id", "year", "replicate",
        "yield_value", "bio_yield", "pod_per_plant",
    ]
    writer.writerow(headers)
    for row in measurements:
        writer.writerow([row.get(header, "") for header in headers])

    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    filename_part = "".join(
        character for character in selected_trial
        if character.isalnum() or character in "-_"
    )
    filename = f"researcher-measurements-{filename_part}.csv" if filename_part else "researcher-measurements.csv"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@app.route("/dalrrd-dashboard")
def dalrrd_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    trials = supabase.table("trial").select("*").execute().data or []
    sites = supabase.table("trial_sites").select("*").execute().data or []
    treatments = supabase.table("treatment").select("trial_id,treatment_name").execute().data or []

    trial_by_id = {str(t.get("trial_id")): t for t in trials}
    treatments_by_trial = {}
    for treatment in treatments:
        treatments_by_trial.setdefault(str(treatment.get("trial_id")), []).append(
            treatment.get("treatment_name") or "Unnamed treatment"
        )

    review_by_trial = {}
    try:
        reviews = (
            supabase.table("trial_review")
            .select("*")
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
        for review in reviews:
            review_by_trial.setdefault(str(review.get("trial_id")), review)
    except Exception:
        app.logger.exception("Could not load trial_review")

    active_trial = trials[0].get("trial_code") if trials else None
    return render_template(
        "DALRRDdashboard.html",
        trials=trials,
        sites=sites,
        trial_by_id=trial_by_id,
        treatments_by_trial=treatments_by_trial,
        review_by_trial=review_by_trial,
        active_trial=active_trial,
    )


def _save_review(trial_id, status, comment=None):
    supabase.table("trial_review").insert({
        "trial_id": trial_id,
        "status": status,
        "comment": comment,
        "reviewed_by": session.get("user_id"),
    }).execute()


@app.route("/verify-trial/<trial_id>", methods=["POST"])
def verify_trial(trial_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    try:
        _save_review(trial_id, "verified")
        flash("Trial verified.", "success")
    except Exception:
        app.logger.exception("Verify failed")
        flash("Could not save the verification. Check the server log.", "error")
    return redirect(url_for("dalrrd_dashboard"))


@app.route("/query-trial/<trial_id>", methods=["POST"])
def query_trial(trial_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    message = (request.form.get("message") or "").strip()
    if not message:
        flash("Please enter a query before submitting.", "error")
        return redirect(url_for("dalrrd_dashboard"))
    try:
        _save_review(trial_id, "queried", message)
        flash("Query submitted.", "success")
    except Exception:
        app.logger.exception("Query failed")
        flash("Could not save the query. Check the server log.", "error")
    return redirect(url_for("dalrrd_dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def pdf(lines):
    """Create a small text PDF using only Python's standard library."""
    import textwrap

    wrapped_lines = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(str(line), width=92) or [""])
    lines_per_page = 52
    pages = [wrapped_lines[index:index + lines_per_page]
             for index in range(0, len(wrapped_lines), lines_per_page)] or [[]]

    objects = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    page_ids = [4 + index * 2 for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for index, page_lines in enumerate(pages):
        page_id = 4 + index * 2
        content_id = page_id + 1
        commands = ["BT", "/F1 10 Tf", "50 750 Td", "13 TL"]
        for line in page_lines:
            safe_text = str(line).encode("ascii", "replace").decode("ascii")
            escaped = safe_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
            commands.append("T*")
        commands.append("ET")
        content = "\n".join(commands).encode("ascii")
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        objects[content_id] = (
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content + b"\nendstream"
        )

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(objects[object_id])
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)
@app.route("/download-dalrrd-report")
def download_dalrrd_report():
    if "user_id" not in session:
        return redirect(url_for("login"))

    trials = supabase.table("trial").select("*").execute().data or []
    sites = supabase.table("trial_sites").select("*").execute().data or []
    treatments = supabase.table("treatment").select("*").execute().data or []
    measurements = supabase.table("measurement").select("*").execute().data or []

    sites_by_trial = {}
    for site in sites:
        sites_by_trial.setdefault(str(site.get("trial_id")), []).append(site)
    treatments_by_trial = {}
    treatment_by_id = {}
    for treatment in treatments:
        trial_key = str(treatment.get("trial_id"))
        treatments_by_trial.setdefault(trial_key, []).append(treatment)
        treatment_by_id[str(treatment.get("treatment_id"))] = treatment
    measurements_by_treatment = {}
    for measurement in measurements:
        measurements_by_treatment.setdefault(
            str(measurement.get("treatment_id")), []
        ).append(measurement)

    lines = [
        "AgriTrial - DALRRD Review Report",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')} (South African time)",
        f"Trials: {len(trials)} | Trial sites: {len(sites)} | Measurements: {len(measurements)}",
        "",
    ]
    for trial in trials:
        trial_id = str(trial.get("trial_id"))
        lines.extend([
            f"Trial: {trial.get('trial_name') or 'Unnamed trial'}",
            f"Code: {trial.get('trial_code') or 'Not provided'} | Crop: {trial.get('target_crop') or 'Not provided'}",
        ])
        trial_sites = sites_by_trial.get(trial_id, [])
        if trial_sites:
            lines.append("Sites:")
            for site in trial_sites:
                lines.append(
                    f"  {site.get('site_name') or 'Unnamed site'} | Farm: {site.get('farm_name') or 'Not provided'} | "
                    f"Farmer: {site.get('farmer_name') or 'Not provided'} | Soil: {site.get('soil_type') or 'Not provided'}"
                )
        trial_treatments = treatments_by_trial.get(trial_id, [])
        if trial_treatments:
            lines.append("Treatments and measurements:")
            for treatment in trial_treatments:
                lines.append(f"  Treatment: {treatment.get('treatment_name') or 'Unnamed treatment'}")
                for measurement in measurements_by_treatment.get(str(treatment.get("treatment_id")), []):
                    lines.append(
                        f"    Year: {measurement.get('year', 'N/A')} | Yield: {measurement.get('yield_value', 'N/A')} | "
                        f"Bio yield: {measurement.get('bio_yield', 'N/A')} | Pods per plant: {measurement.get('pod_per_plant', 'N/A')}"
                    )
        lines.append("")

    response = make_response(pdf(lines))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = 'attachment; filename="dalrrd-trial-report.pdf"'
    return response

@app.route("/investor-dashboard")
def investor_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("Investordashboard.html")


@app.route("/partner-dashboard")
def partner_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    sites = supabase.table("trial_sites").select("*").execute().data or []
    treatments = supabase.table("treatment").select("*").execute().data or []
    return render_template(
        "Partnerdashboard.html",
        sites=sites,
        treatments=treatments,
    )


@app.route("/submit", methods=["POST"])
def submit():
    payload = request.form.to_dict(flat=True)
    try:
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            photo_bytes = photo_file.read(8 * 1024 * 1024 + 1)
            if len(photo_bytes) > 8 * 1024 * 1024:
                return "The photo must be 8 MB or smaller.", 413
            if not photo_bytes:
                return "The selected photo is empty. Choose it again and retry.", 400
            content_type = (photo_file.mimetype or "").lower()
            allowed_image_types = {
                "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"
            }
            if content_type not in allowed_image_types:
                return "Choose a JPEG, PNG, WebP, HEIC, or HEIF image.", 400
            payload["_photo_base64"] = base64.b64encode(photo_bytes).decode("ascii")
            payload["_photo_filename"] = secure_filename(photo_file.filename)[:255]
            payload["_photo_content_type"] = content_type
            payload["_photo_key"] = str(uuid.uuid4())

        payload["trial_code"] = (payload.get("trial_code") or "").strip()
        payload["site_name"] = (payload.get("site_name") or "").strip()
        payload["treatment_name"] = (payload.get("treatment_name") or "").strip()
        if not payload["trial_code"] or not payload["site_name"] or not payload["treatment_name"]:
            return "Trial code, site name, and treatment name are required.", 400

        for field in ("year", "replicate", "replication_number", "plot_number", "treatment_number", "total_replications", "row_index", "column_index"):
            if payload.get(field):
                int(payload[field])
        for field in ("latitude", "longitude", "application_rate", "yield_value", "bio_yield", "pods_per_plant"):
            if payload.get(field):
                float(payload[field])
        for field in ("start_date", "end_date", "scheduled_date", "completed_date", "measurement_date"):
            if payload.get(field):
                time.strptime(payload[field], "%Y-%m-%d")

        payload["year"] = payload.get("year") or str(time.localtime().tm_year)
        payload["replicate"] = payload.get("replicate") or payload.get("replication_number") or "1"
        payload["plot_number"] = payload.get("plot_number") or "1"
        payload["replication_number"] = payload.get("replication_number") or payload["replicate"]
        if session.get("offline"):
            save_submission_offline(session["user_id"], payload)
            flash("Entry saved on this device. Reconnect, sign in online, then sync it.", "warning")
            return redirect(url_for("capture"))

        trial_values = _nonblank_fields({
            "trial_code": payload["trial_code"],
            "trial_name": (payload.get("trial_name") or "").strip(),
            "target_crop": (payload.get("target_crop") or "").strip(),
            "objective": (payload.get("objective") or "").strip(),
            "start_date": payload.get("start_date") or None,
            "end_date": payload.get("end_date") or None,
            "status": (payload.get("status") or "Active").strip(),
        })
        trial_rows = (
            supabase.table("trial").select("*")
            .eq("trial_code", payload["trial_code"]).limit(1).execute().data or []
        )
        if trial_rows:
            trial_id = trial_rows[0]["trial_id"]
            supabase.table("trial").update(trial_values).eq("trial_id", trial_id).execute()
        else:
            trial_id = _insert_one("trial", trial_values, "trial_id")

        farm_name = (payload.get("farm_name") or "").strip()
        site_rows = supabase.table("trial_sites").select("*").eq("trial_id", trial_id).execute().data or []
        site = next((row for row in site_rows
                     if (row.get("site_name") or "").strip().casefold() == payload["site_name"].casefold()
                     and (row.get("farm_name") or "").strip().casefold() == farm_name.casefold()), None)
        site_values = _nonblank_fields({
            "trial_id": trial_id,
            "farmer_name": (payload.get("farmer_name") or "").strip(),
            "farm_name": farm_name,
            "site_name": payload["site_name"],
            "latitude": float(payload["latitude"]) if payload.get("latitude") else None,
            "longitude": float(payload["longitude"]) if payload.get("longitude") else None,
            "soil_type": (payload.get("soil_type") or "").strip(),
            "previous_crop": (payload.get("previous_crop") or "").strip(),
            "experimental_design": (payload.get("experimental_design") or "").strip(),
            "total_replications": int(payload["total_replications"]) if payload.get("total_replications") else None,
        })
        if site:
            site_id = site["site_id"]
            supabase.table("trial_sites").update(site_values).eq("site_id", site_id).execute()
        else:
            site_id = _insert_one("trial_sites", site_values, "site_id")

        treatment_name = (payload.get("treatment_name") or "").strip()
        treatment_rows = supabase.table("treatment").select("*").eq("trial_id", trial_id).execute().data or []
        treatment = next((row for row in treatment_rows
                          if (row.get("treatment_name") or "").strip().casefold() == treatment_name.casefold()), None)
        treatment_values = _nonblank_fields({
            "trial_id": trial_id,
            "treatment_number": int(payload["treatment_number"]) if payload.get("treatment_number") else None,
            "treatment_name": treatment_name,
            "formulation_details": (payload.get("formulation_details") or "").strip(),
            "application_rate": float(payload["application_rate"]) if payload.get("application_rate") else None,
            "rate_unit": (payload.get("rate_unit") or "").strip(),
        })
        if treatment:
            treatment_id = treatment["treatment_id"]
            supabase.table("treatment").update(treatment_values).eq("treatment_id", treatment_id).execute()
        else:
            treatment_id = _insert_one("treatment", treatment_values, "treatment_id")

        replicate = int(payload["replicate"])
        plot_number = int(payload["plot_number"])
        plot_rows = (
            supabase.table("plots").select("*")
            .eq("site_id", site_id).eq("treatment_id", treatment_id)
            .eq("plot_number", plot_number).eq("replication_number", replicate)
            .limit(1).execute().data or []
        )
        plot_values = _nonblank_fields({
            "site_id": site_id,
            "treatment_id": treatment_id,
            "plot_number": plot_number,
            "replication_number": replicate,
            "row_index": int(payload["row_index"]) if payload.get("row_index") else None,
            "column_index": int(payload["column_index"]) if payload.get("column_index") else None,
        })
        if plot_rows:
            plot_id = plot_rows[0]["plot_id"]
            supabase.table("plots").update(plot_values).eq("plot_id", plot_id).execute()
        else:
            plot_id = _insert_one("plots", plot_values, "plot_id")

        save_trait_and_schedule(supabase, trial_id, payload, session.get("user_id"))

        metric_fields = {
            "yield_value": payload.get("yield_value"),
            "bio_yield": payload.get("bio_yield"),
            "pod_per_plant": payload.get("pods_per_plant"),
        }
        has_measurement = any(value not in (None, "") for value in metric_fields.values())
        has_measurement = has_measurement or bool(payload.get("measurement_date"))
        if has_measurement:
            measurement = {
                "treatment_id": treatment_id,
                "year": int(payload["year"]),
                "replicate": replicate,
            }
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
                supabase, payload, trial_id, site_id, treatment_id, plot_id,
                session.get("user_id"),
            )

        flash("Trial entry saved. Submitted details are stored and the dashboard reflects saved measurements.", "success")
        return redirect(url_for("farmer_dashboard", updated="1"))

    except (httpx.NetworkError, httpx.TimeoutException):
        session["offline"] = True
        try:
            save_submission_offline(session["user_id"], payload)
            flash("The connection dropped. Your full entry, including its photo, was queued on this device; reconnect and sync it.", "warning")
            return redirect(url_for("capture"))
        except Exception:
            app.logger.exception("Could not queue offline farmer submission")
            return "The connection failed and this entry could not be queued locally. Keep this page open and try again.", 503
    except (TypeError, ValueError):
        app.logger.exception("Invalid trial submission")
        return "A number, date, or photo was invalid. Check the fields and try again.", 400
    except Exception:
        app.logger.exception("Trial submission failed")
        return "Submission failed. Check the server log; some trial details may already have been saved.", 500

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = (request.form.get("role") or "").strip().lower()
        known_roles = {"farmer", "researcher", "uwc", "su_arise", "investor", "funder", "partner", "dalrrd"}
        if role not in known_roles:
            flash("Please choose a role.", "error")
            return redirect(url_for("register"))
        try:
            supabase.auth.sign_up({
                "email": request.form["email"].strip(),
                "password": request.form["password"],
                "options": {
                    "data": {
                        "display_name": request.form.get("name", "").strip(),
                        "requested_role": role,
                    }
                }
            })
            flash("Account created. If email confirmation is enabled, confirm your email, then sign in.", "success")
            return redirect(url_for("login"))
        except Exception:
            app.logger.exception("Registration failed")
            flash("Registration failed. Check the server terminal for the specific Supabase error.", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/success", methods=["GET"])
def success():
    data = {
        "plot_id": request.args.get("plot_id", "N/A"),
        "variety": request.args.get("variety", "N/A"),
        "treatment_group": request.args.get("treatment_group", "N/A"),
    }
    return render_template("success.html", data=data)


@app.route("/api/confidence-interval", methods=["GET"])
def confidence_interval():
    _, intervals = measurements_and_ci()
    return jsonify({
        "measurement": "Yield",
        "confidence_level": 0.95,
        "results": intervals,
    })
@app.route("/sync-data", methods=["POST"])
def sync_data():
    email = session.get("email", "")
    password = request.form.get("password", "")
    try:
        auth = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if str(auth.user.id) != str(session.get("user_id")):
            return "This password belongs to a different account.", 403
        metadata = getattr(auth.user, "user_metadata", None) or {}
        app_metadata = getattr(auth.user, "app_metadata", None) or {}
        role = str(metadata.get("requested_role") or metadata.get("role") or app_metadata.get("role") or "").strip().lower()
        if role != "farmer":
            return "Only an approved farmer account can sync farmer entries.", 403
        synced = sync_pending_submissions(supabase, auth.user.id)
        session["offline"] = False
        flash(f"Sync complete. {synced} queued entr{'y' if synced == 1 else 'ies'} uploaded.", "success")
    except (httpx.NetworkError, httpx.TimeoutException):
        session["offline"] = True
        flash("Still offline. Your queued entries remain saved on this device.", "error")
    except Exception:
        app.logger.exception("Offline submission sync failed")
        flash("Sync failed. Unsent entries were kept on this device for another attempt.", "error")
    return redirect(url_for("farmer_dashboard" if not session.get("offline") else "capture"))

if __name__ == "__main__":
    # One local development server; phones can reach it over the same Wi-Fi.
    app.run(host="0.0.0.0", port=5000, debug=False)
