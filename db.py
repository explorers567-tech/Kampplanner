import os
import secrets
import sqlite3
from collections import Counter, defaultdict

DB_PAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "kampplanner.db")

# ---------- indeling van de dag (in minuten sinds middernacht) ----------
# Pas deze waarden aan als de grenzen anders moeten.
NACHT_START = 0 * 60 + 30     # 00:30  (daarvoor hoort het nog bij de avond)
NACHT_EINDE = 7 * 60 + 30     # 07:30  (vanaf hier ochtend)
OCHTEND_EINDE = 12 * 60       # 12:00
MIDDAG_EINDE = 18 * 60        # 18:00

DAGDEELNAMEN = {"ochtend": "Ochtend", "middag": "Middag", "avond": "Avond", "nacht": "Nacht"}
DAGDEELVOLGORDE = ["ochtend", "middag", "avond", "nacht"]


def dagdeel_van(start):
    """'19:30' -> 'avond', '00:15' -> 'avond', '00:30' -> 'nacht', '07:50' -> 'ochtend'."""
    uur, minuut = (int(x) for x in start.split(":")[:2])
    m = uur * 60 + minuut
    if m < NACHT_START:
        return "avond"
    if m < NACHT_EINDE:
        return "nacht"
    if m < OCHTEND_EINDE:
        return "ochtend"
    if m < MIDDAG_EINDE:
        return "middag"
    return "avond"


def verbind():
    con = sqlite3.connect(DB_PAD)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# ---------- overzichten ----------

def haal_telling():
    con = verbind()
    rijen = con.execute("""
        SELECT p.naam, r.code, COUNT(*) AS aantal
        FROM assignments a
        JOIN persons p ON p.id = a.person_id
        JOIN roles   r ON r.code = a.role_id
        WHERE a.role_id NOT IN ('#', '?')
        GROUP BY p.naam, r.code
        ORDER BY p.naam, aantal DESC
    """).fetchall()
    con.close()
    return rijen


def haal_schema():
    con = verbind()
    slots = con.execute(
        "SELECT id, dag, start, titel, aantal FROM slots ORDER BY volgorde"
    ).fetchall()
    personen = con.execute("SELECT id, naam FROM persons ORDER BY id").fetchall()
    cellen = {
        (r["slot_id"], r["person_id"]): r["role_id"]
        for r in con.execute("SELECT slot_id, person_id, role_id FROM assignments")
    }
    con.close()
    return slots, personen, cellen


def haal_persoonlijk(person_id):
    con = verbind()
    persoon = con.execute(
        "SELECT id, naam FROM persons WHERE id = ?", (person_id,)
    ).fetchone()
    rijen = con.execute("""
        SELECT s.dag, s.start, s.titel, a.role_id AS code, r.omschrijving
        FROM assignments a
        JOIN slots s ON s.id = a.slot_id
        LEFT JOIN roles r ON r.code = a.role_id
        WHERE a.person_id = ?
          AND a.role_id NOT IN ('#', '?')
        ORDER BY s.volgorde
    """, (person_id,)).fetchall()
    con.close()
    return persoon, rijen


# ---------- aanwezigheid per dagdeel ----------

def haal_dagdelen():
    """Lijst (dag, dagdeel) in volgorde van het kamp, afgeleid uit de slots.
    Elke dag behalve de laatste krijgt ook een nacht, ook als er geen slot in valt."""
    con = verbind()
    slots = con.execute("SELECT dag, start FROM slots ORDER BY volgorde").fetchall()
    con.close()
    per_dag = {}
    for s in slots:
        lijst = per_dag.setdefault(s["dag"], [])
        dd = dagdeel_van(s["start"])
        if dd not in lijst:
            lijst.append(dd)
    dagen = list(per_dag)
    uit = []
    for i, dag in enumerate(dagen):
        lijst = per_dag[dag]
        if "nacht" not in lijst and i < len(dagen) - 1:
            lijst.append("nacht")
        for dd in sorted(lijst, key=DAGDEELVOLGORDE.index):
            uit.append((dag, dd))
    return uit


def haal_beschikbaarheid(person_id):
    con = verbind()
    persoon = con.execute(
        "SELECT id, naam FROM persons WHERE id = ?", (person_id,)
    ).fetchone()
    keuzes = {
        (r["dag"], r["dagdeel"]): r["status"]
        for r in con.execute(
            "SELECT dag, dagdeel, status FROM aanwezigheid WHERE person_id = ?",
            (person_id,))
    }
    uploads = con.execute("""
        SELECT id, originele_naam, geupload_op
        FROM uploads WHERE person_id = ? ORDER BY id DESC
    """, (person_id,)).fetchall()
    con.close()
    dagdelen = [
        {"dag": d, "dagdeel": dd, "naam": DAGDEELNAMEN[dd],
         "veld": f"dd_{d}_{dd}", "status": keuzes.get((d, dd), "")}
        for d, dd in haal_dagdelen()
    ]
    return persoon, dagdelen, uploads


def sla_beschikbaarheid_op(person_id, invoer):
    """invoer = lijst van (dag, dagdeel, status); lege status wist de keuze."""
    con = verbind()
    try:
        for dag, dagdeel, status in invoer:
            if status == "":
                con.execute(
                    "DELETE FROM aanwezigheid WHERE person_id = ? AND dag = ? AND dagdeel = ?",
                    (person_id, dag, dagdeel))
            else:
                con.execute("""
                    INSERT INTO aanwezigheid (person_id, dag, dagdeel, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(person_id, dag, dagdeel)
                    DO UPDATE SET status = excluded.status
                """, (person_id, dag, dagdeel, status))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---------- uploads ----------

def sla_upload_op(person_id, originele_naam, opslag_naam):
    con = verbind()
    con.execute(
        "INSERT INTO uploads (person_id, originele_naam, opslag_naam) VALUES (?, ?, ?)",
        (person_id, originele_naam, opslag_naam))
    con.commit()
    con.close()


def haal_upload(upload_id):
    con = verbind()
    rij = con.execute(
        "SELECT person_id, originele_naam, opslag_naam FROM uploads WHERE id = ?",
        (upload_id,)).fetchone()
    con.close()
    return rij


def verwijder_upload(upload_id):
    con = verbind()
    rij = con.execute(
        "SELECT person_id, opslag_naam FROM uploads WHERE id = ?", (upload_id,)
    ).fetchone()
    if rij:
        con.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
        con.commit()
    con.close()
    return rij


# ---------- inloggen ----------

def vind_persoon_op_token(token):
    con = verbind()
    rij = con.execute("SELECT id, naam FROM persons WHERE token = ?", (token,)).fetchone()
    con.close()
    return rij


def vind_admin(gebruikersnaam):
    con = verbind()
    rij = con.execute(
        "SELECT id, wachtwoord_hash FROM admins WHERE gebruikersnaam = ?",
        (gebruikersnaam,)).fetchone()
    con.close()
    return rij


# ---------- beheer: personen ----------

def haal_personen_beheer():
    con = verbind()
    rijen = con.execute("""
        SELECT p.id, p.naam, p.is_ouderraad, p.token,
               (SELECT group_concat(sp.naam, ', ')
                  FROM persoon_speltak ps JOIN speltakken sp ON sp.id = ps.speltak_id
                 WHERE ps.person_id = p.id) AS speltak,
               (SELECT COUNT(*) FROM aanwezigheid a WHERE a.person_id = p.id) AS n_beschikbaar,
               (SELECT COUNT(*) FROM uploads u WHERE u.person_id = p.id)      AS n_uploads,
               (SELECT COUNT(*) FROM persoon_organisatie po WHERE po.person_id = p.id) AS n_org
        FROM persons p
        ORDER BY p.naam
    """).fetchall()
    con.close()
    return rijen


def voeg_persoon_toe(naam, is_ouderraad):
    con = verbind()
    try:
        con.execute(
            "INSERT INTO persons (naam, is_ouderraad, token) VALUES (?, ?, ?)",
            (naam, is_ouderraad, secrets.token_urlsafe(16)))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ValueError(f"Er bestaat al iemand met de naam {naam}.")
    finally:
        con.close()


def wijzig_persoon(person_id, naam, is_ouderraad):
    con = verbind()
    try:
        con.execute("UPDATE persons SET naam = ?, is_ouderraad = ? WHERE id = ?",
                    (naam, is_ouderraad, person_id))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ValueError(f"Er bestaat al iemand met de naam {naam}.")
    finally:
        con.close()
        
def nieuw_token(person_id):
    con = verbind()
    con.execute("UPDATE persons SET token = ? WHERE id = ?",
                (secrets.token_urlsafe(16), person_id))
    con.commit()
    con.close()


def verwijder_persoon(person_id):
    """Verwijdert de persoon met alles wat eraan hangt.
    Geeft de bestandsnamen terug die van schijf verwijderd moeten worden."""
    con = verbind()
    try:
        bestanden = [r["opslag_naam"] for r in con.execute(
            "SELECT opslag_naam FROM uploads WHERE person_id = ?", (person_id,))]
        for tabel in ("aanwezigheid", "persoon_organisatie", "persoon_speltak",
                      "availability", "uploads", "assignments"):
            con.execute(f"DELETE FROM {tabel} WHERE person_id = ?", (person_id,))
        con.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return bestanden


def haal_persoon_profiel(person_id):
    """Persoon + alle speltakken en organisaties, elk met 'gekozen' (0 of 1)."""
    con = verbind()
    persoon = con.execute(
        "SELECT id, naam FROM persons WHERE id = ?", (person_id,)
    ).fetchone()
    if persoon is None:
        con.close()
        return None, [], []
    speltakken = con.execute("""
        SELECT sp.id, sp.naam, sp.min_leiding,
               EXISTS (SELECT 1 FROM persoon_speltak ps
                        WHERE ps.person_id = ? AND ps.speltak_id = sp.id) AS gekozen
        FROM speltakken sp ORDER BY sp.id
    """, (person_id,)).fetchall()
    organisaties = con.execute("""
        SELECT o.id, o.naam,
               EXISTS (SELECT 1 FROM persoon_organisatie po
                        WHERE po.person_id = ? AND po.organisatie_id = o.id) AS gekozen
        FROM organisaties o
        ORDER BY COALESCE((SELECT MIN(s.volgorde) FROM organisatie_slots os
                             JOIN slots s ON s.id = os.slot_id
                            WHERE os.organisatie_id = o.id), 9999), o.id
    """, (person_id,)).fetchall()
    con.close()
    return persoon, speltakken, organisaties


def sla_persoon_profiel_op(person_id, speltak_ids, organisatie_ids):
    con = verbind()
    try:
        con.execute("DELETE FROM persoon_speltak WHERE person_id = ?", (person_id,))
        for sid in speltak_ids:
            con.execute(
                "INSERT OR IGNORE INTO persoon_speltak (person_id, speltak_id) VALUES (?, ?)",
                (person_id, sid))
        con.execute("DELETE FROM persoon_organisatie WHERE person_id = ?", (person_id,))
        for oid in organisatie_ids:
            con.execute(
                "INSERT OR IGNORE INTO persoon_organisatie (person_id, organisatie_id) VALUES (?, ?)",
                (person_id, oid))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def geldige_speltak_ids():
    con = verbind()
    ids = {r["id"] for r in con.execute("SELECT id FROM speltakken")}
    con.close()
    return ids


def geldige_organisatie_ids():
    con = verbind()
    ids = {r["id"] for r in con.execute("SELECT id FROM organisaties")}
    con.close()
    return ids


# ---------- beheer: activiteiten (organisaties) ----------

def haal_organisaties():
    con = verbind()
    rijen = con.execute("""
        SELECT o.id, o.naam,
               (SELECT COUNT(*) FROM organisatie_slots os WHERE os.organisatie_id = o.id) AS n_slots,
               (SELECT group_concat(p.naam, ', ')
                  FROM persoon_organisatie po JOIN persons p ON p.id = po.person_id
                 WHERE po.organisatie_id = o.id) AS organisatoren
        FROM organisaties o
        ORDER BY COALESCE((SELECT MIN(s.volgorde) FROM organisatie_slots os
                             JOIN slots s ON s.id = os.slot_id
                            WHERE os.organisatie_id = o.id), 9999), o.id
    """).fetchall()
    con.close()
    return rijen


def maak_organisatie(naam):
    """Geeft het nieuwe id terug; ValueError als de naam al bestaat."""
    con = verbind()
    try:
        cur = con.execute("INSERT INTO organisaties (naam) VALUES (?)", (naam,))
        con.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Er bestaat al een activiteit met deze naam.")
    finally:
        con.close()


def haal_organisatie(org_id):
    """Organisatie + alle slots (met huidige rolcode of '') + alle personen (gekozen of niet)."""
    con = verbind()
    org = con.execute("SELECT id, naam FROM organisaties WHERE id = ?", (org_id,)).fetchone()
    if org is None:
        con.close()
        return None, [], []
    slots = con.execute("""
        SELECT s.id, s.dag, s.start, s.titel,
               COALESCE((SELECT os.rol_code FROM organisatie_slots os
                          WHERE os.organisatie_id = ? AND os.slot_id = s.id), '') AS rol_code
        FROM slots s ORDER BY s.volgorde
    """, (org_id,)).fetchall()
    personen = con.execute("""
        SELECT p.id, p.naam,
               EXISTS (SELECT 1 FROM persoon_organisatie po
                        WHERE po.organisatie_id = ? AND po.person_id = p.id) AS gekozen
        FROM persons p ORDER BY p.naam
    """, (org_id,)).fetchall()
    con.close()
    return org, slots, personen


def sla_organisatie_op(org_id, naam, slot_codes, person_ids):
    """slot_codes = lijst van (slot_id, rolcode); person_ids = organisatoren."""
    con = verbind()
    try:
        con.execute("UPDATE organisaties SET naam = ? WHERE id = ?", (naam, org_id))
        con.execute("DELETE FROM organisatie_slots WHERE organisatie_id = ?", (org_id,))
        for slot_id, code in slot_codes:
            con.execute("INSERT INTO organisatie_slots (organisatie_id, slot_id, rol_code) "
                        "VALUES (?, ?, ?)", (org_id, slot_id, code))
        con.execute("DELETE FROM persoon_organisatie WHERE organisatie_id = ?", (org_id,))
        for pid in person_ids:
            con.execute("INSERT OR IGNORE INTO persoon_organisatie (person_id, organisatie_id) "
                        "VALUES (?, ?)", (pid, org_id))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ValueError("Er bestaat al een activiteit met deze naam.")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def verwijder_organisatie(org_id):
    con = verbind()
    try:
        con.execute("DELETE FROM persoon_organisatie WHERE organisatie_id = ?", (org_id,))
        con.execute("DELETE FROM organisatie_slots WHERE organisatie_id = ?", (org_id,))
        con.execute("DELETE FROM organisaties WHERE id = ?", (org_id,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def haal_persoon_ids():
    con = verbind()
    ids = {r["id"] for r in con.execute("SELECT id FROM persons")}
    con.close()
    return ids


def haal_slot_ids():
    con = verbind()
    ids = {r["id"] for r in con.execute("SELECT id FROM slots")}
    con.close()
    return ids


# ---------- beheer: regels voor slapen en opstaan ----------

def haal_eisen_matrix():
    """Slots, speltakken en welke (slot, speltak)-combinaties een eis hebben."""
    con = verbind()
    slots = con.execute(
        "SELECT id, dag, start, titel FROM slots ORDER BY volgorde").fetchall()
    speltakken = con.execute(
        "SELECT id, naam, min_leiding FROM speltakken ORDER BY id").fetchall()
    eisen = {}
    codes = {}
    for r in con.execute("SELECT slot_id, speltak_id, rol_code FROM slot_eisen"):
        eisen[(r["slot_id"], r["speltak_id"])] = True
        codes[r["slot_id"]] = r["rol_code"]
    con.close()
    return slots, speltakken, eisen, codes


def sla_eisen_op(eisen):
    """eisen = lijst van (slot_id, speltak_id, rolcode); vervangt alle bestaande eisen."""
    con = verbind()
    try:
        con.execute("DELETE FROM slot_eisen")
        for slot_id, speltak_id, code in eisen:
            con.execute("INSERT INTO slot_eisen (slot_id, speltak_id, rol_code) VALUES (?, ?, ?)",
                        (slot_id, speltak_id, code))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---------- beheer: planning ----------

def haal_planning_slots():
    con = verbind()
    slots = con.execute("""
        SELECT s.id, s.dag, s.start, s.titel,
               (SELECT COUNT(*) FROM assignments a
                 WHERE a.slot_id = s.id AND a.role_id NOT IN ('#', '?')) AS n_ingepland
        FROM slots s
        ORDER BY s.volgorde
    """).fetchall()
    ja = Counter((r["dag"], r["dagdeel"]) for r in con.execute(
        "SELECT dag, dagdeel FROM aanwezigheid WHERE status = 'ja'"))
    con.close()
    return [{**dict(s), "n_ja": ja[(s["dag"], dagdeel_van(s["start"]))]} for s in slots]


def haal_rolopties():
    con = verbind()
    rollen = con.execute("SELECT code, omschrijving FROM roles ORDER BY code").fetchall()
    con.close()
    opties = {"#": "Afwezig", "?": "Onbekend"}
    for r in rollen:
        opties[r["code"]] = r["omschrijving"]
    return opties


def haal_slot_planning(slot_id):
    con = verbind()
    slot = con.execute(
        "SELECT id, dag, start, titel FROM slots WHERE id = ?", (slot_id,)
    ).fetchone()
    if slot is None:
        con.close()
        return None, []
    dd = dagdeel_van(slot["start"])
    rijen = con.execute("""
        SELECT p.id, p.naam, p.is_ouderraad,
               (SELECT group_concat(sp.naam, ', ')
                  FROM persoon_speltak ps JOIN speltakken sp ON sp.id = ps.speltak_id
                 WHERE ps.person_id = p.id) AS speltak,
               (SELECT a.role_id FROM assignments a
                 WHERE a.slot_id = ? AND a.person_id = p.id LIMIT 1) AS code,
               (SELECT a.bron FROM assignments a
                 WHERE a.slot_id = ? AND a.person_id = p.id LIMIT 1) AS bron,
               (SELECT v.status FROM aanwezigheid v
                 WHERE v.person_id = p.id AND v.dag = ? AND v.dagdeel = ?) AS status
        FROM persons p
        ORDER BY p.naam
    """, (slot_id, slot_id, slot["dag"], dd)).fetchall()
    con.close()
    return slot, rijen


def sla_planning_op(slot_id, keuzes):
    """keuzes = lijst van (person_id, code); een lege code wist de toewijzing.
    Wat hier wordt opgeslagen telt als handmatig (bron NULL)."""
    con = verbind()
    try:
        for person_id, code in keuzes:
            con.execute("DELETE FROM assignments WHERE slot_id = ? AND person_id = ?",
                        (slot_id, person_id))
            if code:
                con.execute(
                    "INSERT INTO assignments (slot_id, person_id, role_id) VALUES (?, ?, ?)",
                    (slot_id, person_id, code))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---------- automatische indeling ----------

def haal_planner_data():
    con = verbind()
    slots = []
    for r in con.execute("SELECT id, volgorde, dag, start, titel FROM slots ORDER BY volgorde"):
        s = dict(r)
        s["dagdeel"] = dagdeel_van(s["start"])
        slots.append(s)
    personen = {r["id"]: r["naam"] for r in con.execute("SELECT id, naam FROM persons")}
    status = {(r["person_id"], r["dag"], r["dagdeel"]): r["status"]
              for r in con.execute("SELECT person_id, dag, dagdeel, status FROM aanwezigheid")}
    speltakken = {r["id"]: {"naam": r["naam"], "min_leiding": r["min_leiding"]}
                  for r in con.execute("SELECT id, naam, min_leiding FROM speltakken")}
    speltak_leden = defaultdict(list)
    for r in con.execute("SELECT speltak_id, person_id FROM persoon_speltak ORDER BY person_id"):
        speltak_leden[r["speltak_id"]].append(r["person_id"])
    org_slots = [dict(r) for r in con.execute("""
        SELECT os.organisatie_id AS org_id, o.naam AS org_naam, os.slot_id, os.rol_code
        FROM organisatie_slots os JOIN organisaties o ON o.id = os.organisatie_id""")]
    org_leden = defaultdict(list)
    for r in con.execute("SELECT organisatie_id, person_id FROM persoon_organisatie ORDER BY person_id"):
        org_leden[r["organisatie_id"]].append(r["person_id"])
    eisen = [dict(r) for r in con.execute("SELECT slot_id, speltak_id, rol_code FROM slot_eisen")]
    bestaand = {(r["slot_id"], r["person_id"]): r["role_id"]
                for r in con.execute(
                    "SELECT slot_id, person_id, role_id FROM assignments "
                    "WHERE bron IS NULL OR bron != 'auto'")}
    con.close()
    return {"slots": slots, "personen": personen, "status": status,
            "speltakken": speltakken, "speltak_leden": dict(speltak_leden),
            "org_slots": org_slots, "org_leden": dict(org_leden),
            "eisen": eisen, "bestaand": bestaand}


def bewaar_auto_planning(toewijzingen):
    """Vervangt alle eerdere automatische toewijzingen door de nieuwe.
    Handmatige toewijzingen (bron NULL) blijven ongemoeid."""
    con = verbind()
    try:
        con.execute("DELETE FROM assignments WHERE bron = 'auto'")
        for t in toewijzingen:
            con.execute(
                "INSERT INTO assignments (slot_id, person_id, role_id, bron) VALUES (?, ?, ?, 'auto')",
                (t["slot"]["id"], t["person_id"], t["code"]))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def wis_auto_planning():
    con = verbind()
    n = con.execute("DELETE FROM assignments WHERE bron = 'auto'").rowcount
    con.commit()
    con.close()
    return n


def tel_auto_planning():
    con = verbind()
    n = con.execute("SELECT COUNT(*) FROM assignments WHERE bron = 'auto'").fetchone()[0]
    con.close()
    return n

# ---------- aanwezigheid importeren uit Excel ----------

def haal_personen_kort():
    con = verbind()
    rijen = con.execute("SELECT id, naam FROM persons ORDER BY naam").fetchall()
    con.close()
    return [(r["id"], r["naam"]) for r in rijen]


def haal_alle_aanwezigheid():
    con = verbind()
    uit = {(r["person_id"], r["dag"], r["dagdeel"]): r["status"]
           for r in con.execute("SELECT person_id, dag, dagdeel, status FROM aanwezigheid")}
    con.close()
    return uit


def sla_aanwezigheid_import(records):
    """records = lijst van (person_id, dag, dagdeel, status); alles in één transactie."""
    con = verbind()
    try:
        for person_id, dag, dagdeel, status in records:
            con.execute("""
                INSERT INTO aanwezigheid (person_id, dag, dagdeel, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(person_id, dag, dagdeel)
                DO UPDATE SET status = excluded.status
            """, (person_id, dag, dagdeel, status))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()