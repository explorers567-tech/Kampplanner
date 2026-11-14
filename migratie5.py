import sqlite3

con = sqlite3.connect("data/kampplanner.db")
con.execute("PRAGMA foreign_keys = ON")

con.executescript("""
CREATE TABLE IF NOT EXISTS person_roles (
    person_id INTEGER NOT NULL,
    role_code TEXT NOT NULL,
    PRIMARY KEY (person_id, role_code),
    FOREIGN KEY(person_id) REFERENCES persons(id)
);
""")

con.commit()

print("Tabel person_roles aangemaakt of bestaat al.")

for r in con.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
"""):
    print("-", r[0])

con.executescript("""
CREATE TABLE IF NOT EXISTS person_roles (
    person_id INTEGER NOT NULL,
    role_code TEXT NOT NULL,
    PRIMARY KEY (person_id, role_code),
    FOREIGN KEY(person_id) REFERENCES persons(id)
);

CREATE TABLE IF NOT EXISTS leidingrollen (
    code TEXT PRIMARY KEY,
    naam TEXT NOT NULL
);
""")
rollen = [
    ("BL",  "Beverleiding"),
    ("KL",  "Kabouterleiding"),
    ("WL",  "Welpenleiding"),
    ("GL",  "Gidsenleiding"),
    ("VL",  "Verkennerleiding"),
    ("EL",  "Explorerleiding"),
    ("ST",  "Stamlid"),
    ("PS",  "Plusscoutslid"),
    ("BES", "Bestuurslid"),
    ("VRIJ","Vrijwilliger")
]

for code, naam in rollen:
    con.execute("""
        INSERT OR IGNORE INTO leidingrollen
        (code, naam)
        VALUES (?, ?)
    """, (code, naam))
    
con.close()