import getpass
import sqlite3
from werkzeug.security import generate_password_hash

naam = input("Gebruikersnaam voor de beheerder: ").strip()
ww = getpass.getpass("Wachtwoord (minimaal 10 tekens): ")
if not naam or len(ww) < 10:
    raise SystemExit("Gebruikersnaam ontbreekt of wachtwoord is te kort.")

con = sqlite3.connect("data/kampplanner.db")
con.execute("""
    INSERT INTO admins (gebruikersnaam, wachtwoord_hash) VALUES (?, ?)
    ON CONFLICT(gebruikersnaam) DO UPDATE SET wachtwoord_hash = excluded.wachtwoord_hash
""", (naam, generate_password_hash(ww)))
con.commit()
con.close()
print("Beheerder opgeslagen.")