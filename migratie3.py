import re
import sqlite3

con = sqlite3.connect("data/kampplanner.db")
con.execute("PRAGMA foreign_keys = ON")

con.executescript("""
CREATE TABLE IF NOT EXISTS persoon_speltak (
    person_id   INTEGER NOT NULL REFERENCES persons(id),
    speltak_id  INTEGER NOT NULL REFERENCES speltakken(id),
    PRIMARY KEY (person_id, speltak_id)
);

CREATE TABLE IF NOT EXISTS slot_eisen (
    slot_id     INTEGER NOT NULL REFERENCES slots(id),
    speltak_id  INTEGER NOT NULL REFERENCES speltakken(id),
    rol_code    TEXT NOT NULL,
    PRIMARY KEY (slot_id, speltak_id)
);
""")

# assignments.bron: NULL = handmatig, 'auto' = door de automatische indeling
kolommen = [k[1] for k in con.execute("PRAGMA table_info(assignments)")]
if "bron" not in kolommen:
    con.execute("ALTER TABLE assignments ADD COLUMN bron TEXT")

# eerder ingevulde speltak (1 per persoon) overnemen in de nieuwe koppeltabel
if "speltak_id" in [k[1] for k in con.execute("PRAGMA table_info(persons)")]:
    con.execute("""
        INSERT OR IGNORE INTO persoon_speltak (person_id, speltak_id)
        SELECT id, speltak_id FROM persons WHERE speltak_id IS NOT NULL
    """)

# ---- eisen voor slapen en opstaan vullen (alleen als de tabel nog leeg is) ----
if con.execute("SELECT COUNT(*) FROM slot_eisen").fetchone()[0] == 0:
    speltak_id = {r[1]: r[0] for r in con.execute("SELECT id, naam FROM speltakken")}
    ALLE = list(speltak_id)

    def schone_titel(titel):
        return re.split(r"\s{2,}", (titel or "").strip())[0]

    for sid, dag, start, titel in con.execute(
            "SELECT id, dag, start, titel FROM slots ORDER BY volgorde").fetchall():
        t = schone_titel(titel).lower()
        gekozen, code = [], None
        if "naar bed" in t:
            code = "K"
            if "bever" in t:                                   gekozen.append("Bevers")
            if re.search(r"\bkab", t) or "kabouter" in t:      gekozen.append("Kabouters")
            if "welp" in t:                                    gekozen.append("Welpen")
            if re.search(r"\bgid", t):                         gekozen.append("Gidsen")
            if re.search(r"\bver", t):                         gekozen.append("Verkenners")
            if re.search(r"\bexp", t):                         gekozen.append("Explorers")
        elif t.startswith("wekker") or "opstaan" in t:
            code, gekozen = "OK", ALLE
        for naam in gekozen:
            if naam in speltak_id:
                con.execute("INSERT OR IGNORE INTO slot_eisen VALUES (?, ?, ?)",
                            (sid, speltak_id[naam], code))

con.commit()

print("Eisen per slot (aantal leiding per speltak komt uit de tabel speltakken):")
for r in con.execute("""
    SELECT s.dag, s.start, s.titel, e.rol_code, group_concat(sp.naam, ', ')
    FROM slot_eisen e
    JOIN slots s ON s.id = e.slot_id
    JOIN speltakken sp ON sp.id = e.speltak_id
    GROUP BY s.id ORDER BY s.volgorde"""):
    print(f"  {r[0]} {r[1]}  {re.split(chr(92) + 's{2,}', r[2].strip())[0]}  [{r[3]}]  ->  {r[4]}")
con.close()