import csv
import sqlite3

class CanolaDatabase:
    def __init__(self, db_name="canola.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cur = self.conn.cursor()
        
    def setup_tables(self, reset=False):
        if reset:
            self.cur.execute("DROP TABLE IF EXISTS assessment_data")
            self.cur.execute("DROP TABLE IF EXISTS plots")
            self.cur.execute("DROP TABLE IF EXISTS measurement")
            self.cur.execute("DROP TABLE IF EXISTS assessment_traits")
            self.cur.execute("DROP TABLE IF EXISTS treatment")
            self.cur.execute("DROP TABLE IF EXISTS trial_sites")
            self.cur.execute("DROP TABLE IF EXISTS trial")
            
        # Parent: trial table
        self.cur.execute("""CREATE TABLE IF NOT EXISTS trial (
            trial_id INTEGER PRIMARY KEY,
            trial_code VARCHAR,
            trial_name VARCHAR,
            objective TEXT,
            target_crop VARCHAR,
            start_date DATE,
            end_date DATE,
            status VARCHAR,
            created_at DATETIME
        )""")

        # Child: treatment table
        self.cur.execute("""CREATE TABLE IF NOT EXISTS treatment (
            treatment_id INTEGER PRIMARY KEY,
            trial_id INTEGER NOT NULL,
            treatment_number INTEGER,
            treatment_name VARCHAR,
            formulation_details TEXT,
            application_rate DECIMAL,
            rate_unit VARCHAR,
            FOREIGN KEY (trial_id) REFERENCES trial(trial_id)
        )""")
        
        # Child: trial_sites table
        self.cur.execute("""CREATE TABLE IF NOT EXISTS trial_sites (
            site_id INTEGER PRIMARY KEY,
            trial_id INTEGER NOT NULL,
            farmer_name VARCHAR,
            farm_name VARCHER,
            site_name VARCHAR,
            latitude DECIMAL,
            longitude DECIMAL,
            soil_type VARCHAR,
            previous_crop VARCHAR,
            experimental_design VARCHAR,
            total_replications INTEGER,
            FOREIGN KEY (trial_id) REFERENCES trial(trial_id)
        )""")
        # Child: assessment_traits table
        self.cur.execute("""CREATE TABLE IF NOT EXISTS assessment_traits (
            trait_id INTEGER PRIMARY KEY,
            trial_id INTEGER NOT NULL,
            trait_name VARCHAR,
            methodology TEXT,
            unit_of_measure VARCHAR,
            data_type VARCHAR,
            FOREIGN KEY (trial_id) REFERENCES trial(trial_id)
        )""")
        # Child: plots table
        self.cur.execute("""CREATE TABLE IF NOT EXISTS plots (
            plot_id INTEGER PRIMARY KEY,
            site_id INTEGER NOT NULL,
            treatment_id INTEGER NOT NULL,
            plot_number INTEGER,
            replication_number INTEGER,
            row_index INTEGER,
            column_index INTEGER,
            FOREIGN KEY (site_id) REFERENCES trial_sites(site_id),
            FOREIGN KEY (treatment_id) REFERENCES treatment(treatment_id)
        )""")
        # Child: assessment_data
        self.cur.execute("""CREATE TABLE IF NOT EXISTS assessment_data (
            data_id INTEGER PRIMARY KEY,
            plot_id INTEGER NOT NULL,
            trait_id INTEGER NOT NULL,
            assessment_date TEXT,
            numeric_value REAL,
            text_value TEXT,
            collected_by TEXT,
            notes TEXT,
            FOREIGN KEY (plot_id) REFERENCES plots(plot_id),
            FOREIGN KEY (trait_id) REFERENCES assessment_traits(trait_id)
        )""")
        # This is how I'll link the csv measurements with the new tables
        self.cur.execute("""CREATE TABLE IF NOT EXISTS measurement (
            measurement_id INTEGER PRIMARY KEY,
            treatment_id INTEGER NOT NULL,
            year INTEGER,
            replicate INTEGER,
            yield_value REAL,
            bio_yield REAL,
            pod_per_plant REAL,
            seed_per_pod REAL,
            thousand_seed_weight REAL,
            oil_percent REAL,
            oil_yield REAL,
            nitrogen REAL,
            phosphorus REAL,
            potassium REAL,
            sodium REAL,
            calcium REAL,
            magnesium REAL,
            iron REAL,
            manganese REAL,
            zinc REAL,
            copper REAL,
            chlorophyll_a REAL,
            chlorophyll_b REAL,
            rwc REAL,
            ionic_leakage REAL,
            prolin REAL,
            potassium_sodium_ratio REAL,
            FOREIGN KEY (treatment_id) REFERENCES treatment(treatment_id),
            UNIQUE (treatment_id, year, replicate)
        )""")
        self.conn.commit()

    def insert_trial_data(self):
        # Insert Trial
        self.cur.execute('''INSERT OR IGNORE INTO trial (
            trial_id, trial_code, trial_name, objective, target_crop, start_date, end_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            1, 'Canola-25', 'Agri-Canola Fertilizers', 'Compare the effects of treatments on canola measurements', 'Canola', '2025-01-01', '2025-12-31', 'Active', '2026-10-09'
        ))

        # Insert treatments
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''',(
            1, 1, 1, 'Control'
            ))
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''', (
            2, 1, 2, 'Amino acid'
            ))
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''',(
            3, 1, 3, 'Seaweed Extract'
            ))
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''', (
            4, 1, 4, 'Humic acid'
            ))
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''', (
            5, 1, 5, 'Fulvic acid'
            ))
        self.cur.execute('''INSERT OR IGNORE INTO treatment (
            treatment_id, trial_id, treatment_number, treatment_name, formulation_details, application_rate, rate_unit) 
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ''', (
            6, 1, 6, 'Combined'
            ))
        # Insert a trial site
        self.cur.execute("""INSERT OR IGNORE INTO trial_sites (
            site_id, trial_id, farmer_name, farm_name, site_name, latitude, longitude, soil_type,
            previous_crop, experimental_design, total_replications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
            1, 1, "John Doe", "Green Valley Farm", "North field", None, None, None,
            None, None, None
            ))
        # Inserting assessment trait
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (1, 1, 'Yield', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (2, 1, 'Bio Yield', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (3, 1, 'pod/plant', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (4, 1, 'seed/pod', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (5, 1, '1000sw', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (6, 1, 'Oil%', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (7, 1, 'Oil.yield', 'numeric')
            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (8, 1, 'N', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (9, 1, 'P', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (10, 1, 'K', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (11, 1, 'Na', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (12, 1, 'Ca', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (13, 1, 'Mg', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (14, 1, 'Fe', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (15, 1, 'Mn', 'numeric')
                            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (16, 1, 'Zn', 'numeric')
                            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (17, 1, 'Cu', 'numeric')
                            """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (18, 1, 'Chl a', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (19, 1, 'Chl b', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (20, 1, 'RWC', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (21, 1, 'Ionic L', 'numeric')
                    """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (22, 1, 'Prolin', 'numeric')
             """)
        self.cur.execute("""INSERT OR IGNORE INTO assessment_traits (
            trait_id, trial_id, trait_name, data_type) 
            VALUES (23, 1, 'K/Na', 'numeric')
            """)
        self.conn.commit()
    def import_csv(self, csv_file):
        """Import canola measurements from a CSV file into the measurement, plots and assesesmen_data table."""
        required = ["Year", "Block", "Replicates",
            "Yield", "Bio Yield", "pod/plant", "seed/pod", "1000sw", "Oil%",
            "Oil.yield", "N", "P", "K", "Na", "Ca", "Mg", "Fe", "Mn", "Zn",
            "Cu", "Chl a", "Chl b", "RWC", "Ionic L", "Prolin", "K/Na"]
        trait_columns = required[3:]

        # trait_name and trait_id (trait names match the CSV headers)
        trait_ids = {name: trait_id for trait_id, name in self.cur.execute("SELECT trait_id, trait_name FROM assessment_traits")}
        missing_traits = [name for name in trait_columns if name not in trait_ids]
        if missing_traits:
            raise ValueError(f"No assessment_traits entries found: {missing_traits}")
        
        site = self.cur.execute("SELECT site_id FROM trial_sites ORDER BY site_id LIMIT 1").fetchone()
        if site is None:
            raise ValueError("No trial site found. Run insert_trial_data() first.")
        site_id = site[0]
        def normalize_name(value):
            return "".join(character.lower() for character in value.strip() if character.isalnum())
        treatment_ids = {}
        for treatment_id, name in self.cur.execute("SELECT treatment_id,treatment_name FROM treatment"):
            key = normalize_name(name or "")
            if key in treatment_ids and treatment_ids[key] != treatment_id:
                raise ValueError(f"Treatment names are unclear after normalization: {name}")
            treatment_ids[key] = treatment_id
        rows_read = 0
        imported = 0
        skipped = 0
        replaced = 0
        assessments_written = 0

        with open(csv_file, mode="r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("CSV is empty or it has no header row.")
            headers = [header.strip() if header else "" for header in reader.fieldnames]
            if len(headers) != len(set(headers)):
                raise ValueError("CSV contains duplicate column headers")
            reader.fieldnames = headers
            # This is to check the headers once, before importing anything
            missing = [h for h in required if h not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"CSV is missing expected columns: {missing}")
 
            for line_no, row in enumerate(reader, start=2):   # line 1 = header
                rows_read += 1
                def get_value(column):
                    value = row.get(column) 
                    if value is None:
                        return None
                    value = value.strip()
                    return value if value != "" else None
                if None in row:
                    print(f"Line {line_no}: extra values beyond headers are skipped.")
                    skipped += 1
                    continue
            # Find the treatment (ignores extra spaces and capital letters)
                treatment_name = get_value("Block")
                treatment_id = treatment_ids.get(normalize_name(treatment_name or ""))
                if treatment_id is None:
                    known = ", ".join(name for _, name in self.cur.execute("SELECT treatment_id, treatment_name FROM treatment"))
                    print(f"Line {line_no}: treatment '{treatment_name}' not found" f"Known treatments: {known}. Skipped")
                    skipped += 1
                    continue
                
                try:
                    year = int(get_value("Year"))
                    replicate = int(get_value("Replicates"))
                    values = []
                    for header in trait_columns:
                        value = get_value(header)
                        values.append(float(value)if value is not None else None)
                except (TypeError, ValueError):
                    print(f"Line {line_no}: invalid Year measurements or Replicates. Skipped.")
                    skipped += 1
                    continue
           
                # Insert the CSV data into measurement
                self.cur.execute("""INSERT OR REPLACE INTO measurement (
                    treatment_id,
                    year,
                    replicate,
                    yield_value,
                    bio_yield,
                    pod_per_plant,
                    seed_per_pod,
                    thousand_seed_weight,
                    oil_percent,
                    oil_yield,
                    nitrogen,
                    phosphorus,
                    potassium,
                    sodium,
                    calcium,
                    magnesium,
                    iron,
                    manganese,
                    zinc,
                    copper,
                    chlorophyll_a,
                    chlorophyll_b,
                    rwc,
                    ionic_leakage,
                    prolin,
                    potassium_sodium_ratio
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                 treatment_id,
                    get_value("Year"),         
                    get_value("Replicates"),    
                    get_value("Yield"),         
                    get_value("Bio Yield"),     
                    get_value("pod/plant"),     
                    get_value("seed/pod"),      
                    get_value("1000sw"),        
                    get_value("Oil%"),         
                    get_value("Oil.yield"),     
                    get_value("N"),            
                    get_value("P"),
                    get_value("K"),
                    get_value("Na"),
                    get_value("Ca"),
                    get_value("Mg"),
                    get_value("Fe"),
                    get_value("Mn"),
                    get_value("Zn"),
                    get_value("Cu"),
                    get_value("Chl a"),         
                    get_value("Chl b"),         
                    get_value("RWC"),           
                    get_value("Ionic L"),       
                    get_value("Prolin"),        
                    get_value("K/Na")  
                ))
                plot = self.cur.execute("""SELECT plot_id FROM plots WHERE site_id = ? AND treatment_id = ? AND replication_number = ?""", (site_id, treatment_id, replicate)).fetchone()
                if plot is None:
                    plot_number = self.cur.execute("SELECT COALESCE(MAX(plot_number), 0) + 1 FROM plots").fetchone()[0]
                    self.cur.execute("""INSERT INTO plots (site_id, treatment_id, plot_number, replication_number) VALUES (?, ?, ?, ?)""", (site_id, treatment_id, plot_number, replicate))
                    plot_id = self.cur.lastrowid
                else:
                    plot_id = plot[0]
                assessment_date = f"Year {year}"
                for header in trait_columns:
                    value = get_value(header)
                    if value is None:
                        continue
                    try:
                        numeric_value = float(value)
                    except ValueError:
                        print(f"Line {line_no}: '{value}' in '{header}' is not a number. Left out.")
                        continue
                    trait_id = trait_ids[header]
                    #avoiding duplicates if import is run without reset
                    self.cur.execute("""DELETE FROM assessment_data WHERE plot_id = ? and trait_id = ? and assessment_date = ?""", (plot_id, trait_id, assessment_date))
                    self.cur.execute(''' INSERT INTO assessment_data(plot_id, trait_id, assessment_date, numeric_value) VALUES (?, ?, ?, ?)''', (plot_id, trait_id, assessment_date, numeric_value))
                imported += 1
        self.conn.commit()
        print(f"Imported {imported} rows, skipped {skipped}.")
if __name__ == "__main__":
       import os
       BASE = os.path.dirname(os.path.abspath(__file__))
       csv_path = os.path.join(BASE, "AgriTrial+Data+Canola.csv")
       db = CanolaDatabase(os.path.join(BASE, "canola.db"))
       db.setup_tables(reset=True)
       db.insert_trial_data()
       db.import_csv(csv_path)
       print("CSV data imported successfully.")
