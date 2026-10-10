import sqlite3

conn = sqlite3.connect("data/kampplanner.db")
cur = conn.cursor()

for rij in cur.execute("SELECT id, naam, length(naam) FROM persons ORDER BY id"):
    print(rij)
import os
print(os.path.abspath("data/kampplanner.db"))
conn.close()