import sqlite3
con = sqlite3.connect("data/kampplanner.db")
print(con.execute("SELECT * FROM availability LIMIT 5").fetchall())
print(con.execute("SELECT * FROM uploads").fetchall())
con.close()