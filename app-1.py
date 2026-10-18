import os
import sqlite3
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from supabase import create_client
from ci_calculator import results, measurement_label
from data import group_a, group_b
from chart import generate_chart

load_dotenv()

app = Flask(__name__)
DB_NAME = "database.db"

# Initialize Supabase Client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def get_db_connection():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  """Initializes the SQLite database with all 7 required relational tables."""
  conn = get_db_connection()
  cursor = conn.cursor()

  # 1. Trial Site Table (Metadata & Context)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS trial_sites (
            site_id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_name TEXT,
            farm_name TEXT,
            site_name TEXT,
            latitude TEXT,
            longitude TEXT,
            soil_type TEXT,
            previous_crop TEXT,
            experimental_design TEXT,
            total_replications INTEGER
        )
    """)

  # 2. Trials Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            trial_code TEXT,
            trial_name TEXT,
            objective TEXT,
            target_crop TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT,
            created_date TEXT,
            FOREIGN KEY (site_id) REFERENCES trial_sites (site_id)
        )
    """)

  # 3. Treatments Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_id INTEGER,
            treatment_number INTEGER,
            treatment_name TEXT,
            formulation_details TEXT,
            application_rate REAL,
            rate_unit TEXT,
            FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
        )
    """)

  # 4. Plots Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS plots (
            plot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            treatment_id INTEGER,
            plot_number INTEGER,
            replication_number INTEGER,
            row_index INTEGER,
            column_index INTEGER,
            FOREIGN KEY (site_id) REFERENCES trial_sites (site_id),
            FOREIGN KEY (treatment_id) REFERENCES treatments (treatment_id)
        )
    """)

  # 5. Assessment Traits Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_traits (
            trait_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trait_name TEXT,
            unit TEXT,
            description TEXT
        )
    """)

  # 6. Assessment Dates Table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_dates (
            assessment_date_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_id INTEGER,
            assessment_stage TEXT,
            scheduled_date TEXT,
            completed_date TEXT,
            FOREIGN KEY (trial_id) REFERENCES trials (trial_id)
        )
    """)

  # 7. Measurements Table (Compliance & Crop Metrics)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER,
            trait_id INTEGER,
            year INTEGER,
            replicate INTEGER,
            yield_value REAL,
            bio_yield REAL,
            pods_per_plant REAL,
            measurement_date TEXT,
            FOREIGN KEY (plot_id) REFERENCES plots (plot_id),
            FOREIGN KEY (trait_id) REFERENCES assessment_traits (trait_id)
        )
    """)

  conn.commit()
  conn.close()

# ── Login page ──
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # No verification needed — prototype just passes through
        return redirect(url_for("capture"))
    return render_template("login.html")

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/capture")
def capture():
    return render_template("index.html")

# Make login the entry point
@app.route("/home")
def home():
    return redirect(url_for("login"))


@app.route("/submit", methods=["POST"])
def submit():
    try:
        # 1. Insert into trial_sites
        site_data = {
            "farmer_name": request.form.get("farmer_name"),
            "farm_name": request.form.get("farm_name"),
            "site_name": request.form.get("site_name"),
            "soil_type": request.form.get("soil_type")
        }
        site_res = supabase.table("trial_sites").insert(site_data).execute()
        site_id = site_res.data[0]["site_id"] if site_res.data else 1

        # 2. Insert into trials
        trial_data = {
            "site_id": site_id,
            "trial_code": request.form.get("trial_code"),
            "trial_name": request.form.get("trial_name"),
            "target_crop": request.form.get("target_crop")
        }
        trial_res = supabase.table("trials").insert(trial_data).execute()
        trial_id = trial_res.data[0]["trial_id"] if trial_res.data else 1

        # 3. Insert into treatments
        treatment_data = {
            "trial_id": trial_id,
            "treatment_name": request.form.get("treatment_name"),
            "application_rate": float(request.form.get("application_rate") or 0.0)
        }
        treatment_res = supabase.table("treatments").insert(treatment_data).execute()
        treatment_id = treatment_res.data[0]["treatment_id"] if treatment_res.data else 1

        # 4. Insert into plots
        plot_data = {
            "site_id": site_id,
            "treatment_id": treatment_id,
            "plot_number": int(request.form.get("plot_number") or 1)
        }
        plot_res = supabase.table("plots").insert(plot_data).execute()
        plot_id = plot_res.data[0]["plot_id"] if plot_res.data else 1

        # 5. Insert into measurements
        measurement_data = {
            "plot_id": plot_id,
            "year": int(request.form.get("year") or 2026),
            "yield_value": float(request.form.get("yield_value") or 0.0),
            "bio_yield": float(request.form.get("bio_yield") or 0.0),
            "pods_per_plant": float(request.form.get("pods_per_plant") or 0.0)
        }
        supabase.table("measurements").insert(measurement_data).execute()

        payload = {
            "plot_id": str(plot_id),
            "variety": request.form.get("target_crop", "N/A"),
            "treatment_group": request.form.get("treatment_name", "N/A"),
        }
        return redirect(url_for("success", **payload))

    except Exception as e:
        print(f"Supabase Insertion Error: {e}")
        payload = {
            "plot_id": request.form.get("plot_id", "N/A"),
            "variety": request.form.get("target_crop", "N/A"),
            "treatment_group": request.form.get("treatment_name", "N/A"),
        }
        return redirect(url_for("success", **payload))


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
    api_results = {}
    for group, values in results.items():
        mean = values["mean"]
        margin = values["ci"]
        api_results[group] = {
            "mean": mean,
            "confidence_interval_margin": margin,
            "lower_bound": round(mean - margin, 2),
            "upper_bound": round(mean + margin, 2)
        }

    return jsonify({
        "measurement": measurement_label,
        "confidence_level": 0.95,
        "results": api_results
    })


@app.route("/dashboard")
def dashboard():
    generate_chart()
    return render_template(
        "dashboard.html",
        measurement=measurement_label,
        sample_size=len(group_a),
        results=results
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)