import sqlite3
from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
DB_NAME = "database.db"


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


@app.route("/")
def index():
  return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
  # Handle form submission across sections and insert into the relational tables
  conn = get_db_connection()
  cursor = conn.cursor()

  # Example data extraction from request.form can be mapped here as your form fields expand
  conn.commit()
  conn.close()
  return redirect(url_for("success"))


@app.route("/success")
def success():
  return render_template("success.html")


@app.route("/dashboard")
def dashboard():
  conn = get_db_connection()
  # Fetch data for dashboard metrics / charts
  conn.close()
  return render_template("dashboard.html")


if __name__ == "__main__":
  init_db()
  app.run(debug=True)
  