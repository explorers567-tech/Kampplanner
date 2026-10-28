import sqlite3, os

pad = "data/kampplanner.db"
print("Huidige map:", os.getcwd())
print("Bestaat:", os.path.exists(pad))
print("Grootte:", os.path.getsize(pad) if os.path.exists(pad) else "-")

con = sqlite3.connect(pad)
print(con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
con.close()

import sqlite3

con = sqlite3.connect("data/kampplanner.db")

for tabel in ["persons", "slots", "roles", "assignments"]:
    print(f"\n{tabel}")
    for kolom in con.execute(f"PRAGMA table_info({tabel})"):
        print("  ", kolom[1], kolom[2])   # naam, type

    print("  voorbeeld:", con.execute(f"SELECT * FROM {tabel} LIMIT 2").fetchall())

con.close()

import sqlite3

con = sqlite3.connect("data/kampplanner.db")

query = """
SELECT p.naam, r.code, COUNT(*) AS aantal
FROM assignments a
JOIN persons p ON p.id = a.person_id
JOIN roles   r ON r.code = a.role_id
GROUP BY p.naam, r.code
ORDER BY p.naam, aantal DESC
"""

for rij in con.execute(query):
    print(rij)

con.close()

import sqlite3

con = sqlite3.connect("data/kampplanner.db")
con.executescript("""
CREATE TABLE IF NOT EXISTS availability (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES persons(id),
    slot_id    INTEGER NOT NULL REFERENCES slots(id),
    status     TEXT NOT NULL CHECK (status IN ('ja', 'nee', 'misschien')),
    opmerking  TEXT,
    UNIQUE (person_id, slot_id)
);

CREATE TABLE IF NOT EXISTS uploads (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id      INTEGER NOT NULL REFERENCES persons(id),
    originele_naam TEXT NOT NULL,
    opslag_naam    TEXT NOT NULL,
    geupload_op    TEXT NOT NULL DEFAULT (datetime('now'))
);
""")
con.commit()
con.close()