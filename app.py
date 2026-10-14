import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
from chart import generate_chart

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    # Generate chart on each load
    generate_chart()
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Capture form values matching new schema
        farmer_name = request.form.get('farmer_name')
        farm_name = request.form.get('farm_name')
        trial_code = request.form.get('trial_code')
        trial_name = request.form.get('trial_name')
        site_name = request.form.get('site_name')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        soil_type = request.form.get('soil_type')
        previous_crop = request.form.get('previous_crop')
        experimental_design = request.form.get('experimental_design')
        total_replications = request.form.get('total_replications')
        
        # Plant Metrics
        plant_height = request.form.get('plant_height')
        yield_val = request.form.get('yield_val')
        spad = request.form.get('spad')
        disease_pct = request.form.get('disease_pct')
        root_mass = request.form.get('root_mass')

        # Environmental & Soil
        ph = request.form.get('ph')
        ec = request.form.get('ec')
        dissolved_o2 = request.form.get('dissolved_o2')
        temperature = request.form.get('temperature')
        humidity = request.form.get('humidity')
        nitrate = request.form.get('nitrate')
        phosphate = request.form.get('phosphate')
        observations = request.form.get('observations')

        # Insert record into database
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trial_code TEXT,
                farmer_name TEXT,
                farm_name TEXT,
                site_name TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO trial_records (trial_code, farmer_name, farm_name, site_name)
            VALUES (?, ?, ?, ?)
        ''', (trial_code, farmer_name, farm_name, site_name))
        
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    # Fetch existing records to display
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_code TEXT,
            farmer_name TEXT,
            farm_name TEXT,
            site_name TEXT
        )
    ''')
    records = cursor.fetchall()
    conn.close()

    return render_template('index.html', records=records)

@app.route('/exit_trial/<int:record_id>', methods=['POST'])
def exit_trial(record_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trial_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/sync_offline', methods=['POST'])
def sync_offline():
    records = request.get_json()
    if not records:
        return jsonify({"status": "no data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    for r in records:
        cursor.execute('''
            INSERT INTO trial_records (trial_code, farmer_name, farm_name, site_name)
            VALUES (?, ?, ?, ?)
        ''', (
            r.get('trial_code'),
            r.get('farmer_name'),
            r.get('farm_name'),
            r.get('site_name')
        ))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "synced_count": len(records)}), 200

if __name__ == '__main__':
    app.run(debug=True)