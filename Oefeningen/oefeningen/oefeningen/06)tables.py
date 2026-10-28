import sqlite3
from datetime import time
from openpyxl import load_workbook

wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active
rijen = list(ws.iter_rows(values_only=True))
kopregel = rijen[0]

conn = sqlite3.connect("data/kampplanner.db")
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

# Eerst assignments weghalen, want die verwijst naar roles
cur.execute("DROP TABLE IF EXISTS assignments")
cur.execute("DROP TABLE IF EXISTS roles")

cur.execute("""
    CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        omschrijving TEXT NOT NULL
    )
""")
cur.execute("""
    CREATE TABLE assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL REFERENCES slots(id),
        person_id INTEGER NOT NULL REFERENCES persons(id),
        role_id TEXT NOT NULL,
        UNIQUE (slot_id, person_id)
    )
""")

roles = {
    "A": "Afwas", 
    "BS": "Brood smeren", 
    "K": "Kids naar bed brengen & oppassen",
    "K*": "Bedden klaarleggen + naar bed brengen", 
    "L": "Aanwezig bij spel als leiding",
    "O": "Organisatie spel", 
    "OA": "Organisatie spel + aanspreekpunt",
    "OK": "Oppassen op kids buiten", 
    "BB": "Bedienen borrel", 
    "BD": "Bedienen diner",
    "#": "Afwezig", 
    "TB": "Toilet beverblokhut", 
    "TS": "Toilet stamkant",
    "TV": "Toilet verkennerkant", 
    "TW": "Toilet welpenblokhut",
    "S": "Stamblokhut opruimen", 
    "M": "Limo/chocomel maken", 
    "V": "Voorbereiding spel",
    "VL": "Voorbereiding + aanwezig bij spel", 
    "XX": "Catering voorbereiden",
    "OD": "Omkleden disco + aanwezig", 
    "OO": "Omkleden disco + opruimen",
    "W": "Alle blokhutten wekken",
}

for code, omschrijving in roles.items():
    cur.execute("INSERT INTO roles (code, omschrijving) VALUES (?, ?)", (code, omschrijving))

person_ids = {naam: pid for pid, naam in cur.execute("SELECT id, naam FROM persons")}
slot_ids = {vgl: sid for sid, vgl in cur.execute("SELECT id, volgorde FROM slots")}

volgorde = 0
for rij in rijen[1:]:
    if not isinstance(rij[1], time):
        continue
    volgorde += 1

    for naam, code in zip(kopregel[4:], rij[4:]):
        if naam is None or code is None:
            continue
        naam = str(naam).strip()
        code = str(code).strip()
        if code == "" or naam not in person_ids:
            continue

        cur.execute(
            "INSERT OR IGNORE INTO assignments (slot_id, person_id, role_id) VALUES (?, ?, ?)",
            (slot_ids[volgorde], person_ids[naam], code)
        )

conn.commit()

print("roles:", cur.execute("SELECT COUNT(*) FROM roles").fetchone()[0])
print("assignments:", cur.execute("SELECT COUNT(*) FROM assignments").fetchone()[0])
conn.close()