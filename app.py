import sqlite3
from flask import Flask, redirect, render_template, request, url_for, jsonify

app = Flask(__name__)


def init_sqlite_db():
  """Initializes the SQLite database with Milestone 1 compliant schema."""
  conn = sqlite3.connect("database.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS trial_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_name TEXT NOT NULL,
            farm_name TEXT NOT NULL,
            plot_id TEXT NOT NULL,
            trial_date TEXT NOT NULL,
            variety TEXT NOT NULL,
            treatment_group TEXT NOT NULL,
            rep TEXT NOT NULL,
            observer TEXT NOT NULL,
            plant_height REAL,
            yield_val REAL,
            spad REAL,
            disease_pct REAL,
            root_mass REAL,
            ph REAL,
            ec REAL,
            dissolved_o2 REAL,
            temp REAL,
            humidity REAL,
            nitrate REAL,
            phosphate REAL,
            notes TEXT
        )
    """)
  conn.commit()
  conn.close()


@app.route("/", methods=["GET", "POST"])
def index():
  if request.method == "POST":
    # Collect form inputs matching Milestone 1 variables
    data = {
        "farmer_name": request.form.get("farmer_name"),
        "farm_name": request.form.get("farm_name"),
        "plot_id": request.form.get("plot_id"),
        "trial_date": request.form.get("trial_date"),
        "variety": request.form.get("variety"),
        "treatment_group": request.form.get("treatment_group"),
        "rep": request.form.get("rep"),
        "observer": request.form.get("observer"),
        "plant_height": request.form.get("plant_height"),
        "yield_val": request.form.get("yield_val"),
        "spad": request.form.get("spad"),
        "disease_pct": request.form.get("disease_pct"),
        "root_mass": request.form.get("root_mass"),
        "ph": request.form.get("ph"),
        "ec": request.form.get("ec"),
        "dissolved_o2": request.form.get("dissolved_o2"),
        "temp": request.form.get("temp"),
        "humidity": request.form.get("humidity"),
        "nitrate": request.form.get("nitrate"),
        "phosphate": request.form.get("phosphate"),
        "notes": request.form.get("notes"),
    }

    # Basic server-side validation
    if not data["plot_id"] or not data["variety"]:
      return render_template(
          "index.html", error="Plot ID and Variety (Crop) are required fields."
      )

    # Insert structured record into local SQLite database (Offline-First MVP)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO trial_records (
            farmer_name, farm_name, plot_id, trial_date, variety, treatment_group, rep, observer,
            plant_height, yield_val, spad, disease_pct, root_mass,
            ph, ec, dissolved_o2, temp, humidity, nitrate, phosphate, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        tuple(data.values()),
    )
    conn.commit()
    conn.close()

    return render_template("success.html", data=data)

  return render_template("index.html")


@app.route('/sync_offline', methods=['POST'])
def sync_offline():
    records = request.get_json()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    for r in records:
        cursor.execute('''
            INSERT INTO trial_data (
                farm_name, farmer_name, plot_id, variety, treatment_group, rep,
                plant_height, yield_val, spad_reading, disease_pct, soil_ph, soil_nitrate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r.get('farm_name'), r.get('farmer_name'), r.get('plot_id'), r.get('variety'),
            r.get('treatment_group'), r.get('rep'), r.get('plant_height'), r.get('yield_val'),
            r.get('spad_reading'), r.get('disease_pct'), r.get('soil_ph'), r.get('soil_nitrate')
        ))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "synced_count": len(records)}), 200
if __name__ == "__main__":
  init_sqlite_db()
  app.run(debug=True)