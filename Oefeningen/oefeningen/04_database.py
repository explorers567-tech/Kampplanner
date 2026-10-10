import sqlite3
from openpyxl import load_workbook

# 1. Namen uit Excel lezen (je code uit oefening 2)
wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active
namen = []

for rij in ws.iter_rows(max_row=1, values_only=True):
    for cel in rij[4:]:
        if cel is not None:
            namen.append(cel)

# 2. Database openen (het bestand wordt aangemaakt als het niet bestaat)
conn = sqlite3.connect("data/kampplanner.db")
cur = conn.cursor()

# 3. Tabel aanmaken
cur.execute("""
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        naam TEXT NOT NULL UNIQUE,
        is_ouderraad INTEGER NOT NULL DEFAULT 0
    )
""")

# 4. Namen invoegen
for naam in namen:
    if naam == "Ouderraad":
        continue
    cur.execute("INSERT OR IGNORE INTO persons (naam) VALUES (?)", (naam,))

# 5. Controleren
for rij in cur.execute("SELECT id, naam FROM persons ORDER BY naam"):
    print(rij)

conn.close()