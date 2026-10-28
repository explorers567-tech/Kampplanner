import sqlite3

con = sqlite3.connect("data/kampplanner.db")
for tabel in ["persons", "slots", "roles", "assignments"]:
    print(tabel, [k[1] for k in con.execute(f"PRAGMA table_info({tabel})")])
    print("  ", con.execute(f"SELECT * FROM {tabel} LIMIT 2").fetchall())
con.close()