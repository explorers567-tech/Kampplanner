import os
import sqlite3
from openpyxl import load_workbook

# 1. Namen uit Excel lezen
wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active
namen = []

for rij in ws.iter_rows(max_row=1, values_only=True):
    for cel in rij[4:]:
        if cel is None:
            continue
        naam = str(cel).strip()
        if naam == "":
            continue
        namen.append(naam)

# 2. Database openen
conn = sqlite3.connect("data/kampplanner.db")
cur = conn.cursor()
print("Database:", os.path.abspath("data/kampplanner.db"))

# 3. Tabel aanmaken
cur.execute("""
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        naam TEXT NOT NULL UNIQUE,
        is_ouderraad INTEGER NOT NULL DEFAULT 0,
        leidingrol TEXT
    )
""")

# 4. Namen invoegen
for naam in namen:
    if naam == "Ouderraad":
        continue
    cur.execute("INSERT OR IGNORE INTO persons (naam) VALUES (?)", (naam,))

conn.commit()

# 5. Controleren (na de commit)
print("Aantal personen:", cur.execute("SELECT COUNT(*) FROM persons").fetchone()[0])

for rij in cur.execute("SELECT id, naam, length(naam) FROM persons ORDER BY id"):
    print(rij)

conn.close()