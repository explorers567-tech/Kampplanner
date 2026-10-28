import re
import sqlite3

con = sqlite3.connect("data/kampplanner.db")
con.execute("PRAGMA foreign_keys = ON")

con.executescript("""
CREATE TABLE IF NOT EXISTS aanwezigheid (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES persons(id),
    dag        TEXT NOT NULL,
    dagdeel    TEXT NOT NULL CHECK (dagdeel IN ('ochtend','middag','avond','nacht')),
    status     TEXT NOT NULL CHECK (status IN ('ja','nee','misschien')),
    UNIQUE (person_id, dag, dagdeel)
);

CREATE TABLE IF NOT EXISTS speltakken (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    naam         TEXT NOT NULL UNIQUE,
    min_leiding  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS organisaties (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    naam  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS organisatie_slots (
    organisatie_id INTEGER NOT NULL REFERENCES organisaties(id),
    slot_id        INTEGER NOT NULL REFERENCES slots(id),
    rol_code       TEXT NOT NULL,
    PRIMARY KEY (organisatie_id, slot_id)
);

CREATE TABLE IF NOT EXISTS persoon_organisatie (
    person_id      INTEGER NOT NULL REFERENCES persons(id),
    organisatie_id INTEGER NOT NULL REFERENCES organisaties(id),
    PRIMARY KEY (person_id, organisatie_id)
);
""")

kolommen = [k[1] for k in con.execute("PRAGMA table_info(persons)")]
if "speltak_id" not in kolommen:
    con.execute("ALTER TABLE persons ADD COLUMN speltak_id INTEGER REFERENCES speltakken(id)")

con.executemany(
    "INSERT OR IGNORE INTO speltakken (naam, min_leiding) VALUES (?, ?)",
    [("Bevers", 2), ("Welpen", 2), ("Kabouters", 2),
     ("Gidsen", 1), ("Verkenners", 1), ("Explorers", 1)],
)

STOPWOORDEN = {"voorbereiden", "voorbereiding", "spel", "uitleg", "met"}


def schone_titel(titel):
    # de locatie staat na 2+ spaties achter de titel
    return re.split(r"\s{2,}", (titel or "").strip())[0]


def kern(titel):
    woorden = [w for w in schone_titel(titel).lower().split() if w not in STOPWOORDEN]
    return " ".join(woorden)


slots = con.execute("SELECT id, dag, titel, volgorde FROM slots ORDER BY volgorde").fetchall()

for s in slots:
    t = schone_titel(s[2]).lower()
    if not (t.startswith("spel") or t == "aandacht"):
        continue
    naam = f"{s[1]} - {schone_titel(s[2])}"
    con.execute("INSERT OR IGNORE INTO organisaties (naam) VALUES (?)", (naam,))
    org_id = con.execute("SELECT id FROM organisaties WHERE naam = ?", (naam,)).fetchone()[0]
    con.execute("INSERT OR IGNORE INTO organisatie_slots VALUES (?, ?, 'O')", (org_id, s[0]))

    for v in slots:
        if v[1] != s[1] or v[0] == s[0]:
            continue
        tv = schone_titel(v[2]).lower()
        if kern(v[2]) != kern(s[2]) or kern(s[2]) == "":
            continue
        if tv.startswith("voorbereid"):
            con.execute("INSERT OR IGNORE INTO organisatie_slots VALUES (?, ?, 'V')", (org_id, v[0]))
        elif tv.startswith("uitleg"):
            con.execute("INSERT OR IGNORE INTO organisatie_slots VALUES (?, ?, 'O')", (org_id, v[0]))

con.commit()

print("Organisaties en bijbehorende slots:")
for o in con.execute("SELECT id, naam FROM organisaties ORDER BY id"):
    print(f"  {o[1]}")
    for r in con.execute("""SELECT os.rol_code, s.start, s.titel FROM organisatie_slots os
                            JOIN slots s ON s.id = os.slot_id WHERE os.organisatie_id = ?
                            ORDER BY s.volgorde""", (o[0],)):
        print(f"      {r[0]}  {r[1]}  {schone_titel(r[2])}")
con.close()