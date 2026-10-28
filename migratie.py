import secrets
import sqlite3

con = sqlite3.connect("data/kampplanner.db")

kolommen = [k[1] for k in con.execute("PRAGMA table_info(persons)")]
if "token" not in kolommen:
    con.execute("ALTER TABLE persons ADD COLUMN token TEXT")

for (pid,) in con.execute("SELECT id FROM persons WHERE token IS NULL").fetchall():
    con.execute("UPDATE persons SET token = ? WHERE id = ?",
                (secrets.token_urlsafe(16), pid))

con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_persons_token ON persons(token)")

con.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    gebruikersnaam  TEXT NOT NULL UNIQUE,
    wachtwoord_hash TEXT NOT NULL
)""")

con.commit()
con.close()
print("Klaar.")