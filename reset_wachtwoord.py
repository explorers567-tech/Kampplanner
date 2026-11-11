from werkzeug.security import generate_password_hash
import sqlite3

nieuw_wachtwoord = "Explorers567!"

con = sqlite3.connect("data/kampplanner.db")

con.execute("""
UPDATE admins
SET wachtwoord_hash = ?
WHERE gebruikersnaam = ?
""", (
    generate_password_hash(nieuw_wachtwoord),
    "admin"
))

con.commit()
con.close()

print("Wachtwoord aangepast.")