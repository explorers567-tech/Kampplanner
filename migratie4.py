import sqlite3

con = sqlite3.connect("data/kampplanner.db")
con.execute("PRAGMA foreign_keys = ON")

con.executescript("""
CREATE TABLE IF NOT EXISTS dagen (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    naam         TEXT NOT NULL UNIQUE,         -- zoals in slots.dag, bv. 'Vrijdag' of 'Opbouwavond 1'
    volgorde     INTEGER NOT NULL,
    soort        TEXT NOT NULL DEFAULT 'kamp'
                 CHECK (soort IN ('kamp', 'voorbereiding', 'opbouw')),
    heeft_nacht  INTEGER NOT NULL DEFAULT 0    -- overnachting: dan ook een 'nacht' bij de aanwezigheid
);

CREATE TABLE IF NOT EXISTS slot_behoefte (
    slot_id   INTEGER NOT NULL REFERENCES slots(id),
    rol_code  TEXT NOT NULL,
    aantal    INTEGER NOT NULL CHECK (aantal > 0),
    PRIMARY KEY (slot_id, rol_code)
);
""")

# de bestaande dagen overnemen, in de volgorde van het kamp
if con.execute("SELECT COUNT(*) FROM dagen").fetchone()[0] == 0:
    dagen = [r[0] for r in con.execute(
        "SELECT dag FROM slots GROUP BY dag ORDER BY MIN(volgorde)")]
    for i, naam in enumerate(dagen, 1):
        # zoals nu: elke kampdag behalve de laatste heeft een nacht
        con.execute("INSERT INTO dagen (naam, volgorde, soort, heeft_nacht) VALUES (?, ?, 'kamp', ?)",
                    (naam, i, 1 if i < len(dagen) else 0))
con.commit()

print("Dagen:")
for r in con.execute("""SELECT d.volgorde, d.naam, d.soort, d.heeft_nacht,
                               (SELECT COUNT(*) FROM slots s WHERE s.dag = d.naam)
                        FROM dagen d ORDER BY d.volgorde"""):
    print(f"  {r[0]}. {r[1]}  [{r[2]}]  overnachting: {'ja' if r[3] else 'nee'}  ({r[4]} slots)")
con.close()