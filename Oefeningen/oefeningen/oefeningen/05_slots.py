import sqlite3
from datetime import time
from openpyxl import load_workbook

wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active

conn = sqlite3.connect("data/kampplanner.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS slots")
cur.execute("""
    CREATE TABLE slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        volgorde INTEGER NOT NULL,
        dag TEXT NOT NULL,
        start TEXT NOT NULL,
        titel TEXT NOT NULL,
        aantal INTEGER
    )
""")

huidige_dag = None
volgorde = 0

for rij in ws.iter_rows(min_row=2, values_only=True):
    if rij[0] is not None:
        huidige_dag = str(rij[0]).strip()

    if not isinstance(rij[1], time):
        continue

    volgorde += 1
    start = rij[1].strftime("%H:%M")
    titel = str(rij[2]).strip()

    cur.execute(
        "INSERT INTO slots (volgorde, dag, start, titel, aantal) VALUES (?, ?, ?, ?, ?)",
        (volgorde, huidige_dag, start, titel, rij[3]),
    )

conn.commit()

for rij in cur.execute("SELECT dag, COUNT(*) FROM slots GROUP BY dag"):
    print(rij)

conn.close()