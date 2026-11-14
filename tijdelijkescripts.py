import sqlite3

con = sqlite3.connect("data/kampplanner.db")

for r in con.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name
"""):
    print(r[0])

con.close()