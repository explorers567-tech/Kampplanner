"""Automatische indeling.

Werkt alleen op gegevens (dicts) en raakt de database niet aan, zodat je eerst
een voorbeeld kunt bekijken. Regels:

1. Organisatoren: wie een spel/activiteit organiseert, krijgt de rolcode van
   elk slot van die organisatie, als die persoon dat dagdeel aanwezig is.
2. Slapen/opstaan: per speltak en per slot (tabel slot_eisen) wordt het aantal
   leiding uit speltakken.min_leiding ingepland. Speltakken worden nooit
   gecombineerd. Handmatige toewijzingen met dezelfde rolcode tellen mee.
3. Alleen 'ja' wordt zonder meer ingepland. 'misschien' alleen als er anders een
   tekort is (en wordt gemarkeerd). 'nee' en niet ingevuld nooit.
4. Handmatige toewijzingen worden nooit overschreven.
"""
import re
import zlib
from collections import Counter, defaultdict

# Rolcodes die voor het tellen als hetzelfde gelden
GELIJK = {"K": {"K", "K*"}, "K*": {"K", "K*"}}


def _groep(code):
    return "K" if code in ("K", "K*") else code

def _lot(slot_id, pid):
    """Vaste, maar per slot wisselende volgorde voor als iedereen even vaak aan de beurt is geweest.
    Zo wint niet steeds iemand met een naam vroeg in het alfabet, en blijft de uitkomst
    bij opnieuw draaien hetzelfde."""
    return zlib.crc32(f"{slot_id}:{pid}".encode())

def maak_planning(d):
    slots = {s["id"]: s for s in d["slots"]}
    volgorde = [s["id"] for s in d["slots"]]
    naam = d["personen"]
    bezet = dict(d["bestaand"])          # (slot, persoon) -> code, handmatig
    nieuw = {}                           # (slot, persoon) -> toewijzing
    meldingen, gezien = [], set()

    teller = Counter()                   # (persoon, rolgroep) -> aantal, voor eerlijk verdelen
    totaal = Counter()                   # persoon -> aantal taken
    for (sid, pid), code in bezet.items():
        if code not in ("#", "?"):
            teller[(pid, _groep(code))] += 1
            totaal[pid] += 1

    def melding(niveau, tekst):
        if tekst not in gezien:
            gezien.add(tekst)
            meldingen.append({"niveau": niveau, "tekst": tekst})

    def status_van(pid, slot):
        return d["status"].get((pid, slot["dag"], slot["dagdeel"]))

    def is_vrij(sid, pid):
        return (sid, pid) not in bezet and (sid, pid) not in nieuw

    def toewijzen(sid, pid, code, reden, onzeker=False):
        nieuw[(sid, pid)] = {"slot": slots[sid], "person_id": pid, "naam": naam[pid],
                             "code": code, "reden": reden, "onzeker": onzeker}
        teller[(pid, _groep(code))] += 1
        totaal[pid] += 1

    def omschrijf(slot):
        # de locatie staat na 2+ spaties achter de titel: alleen de titel tonen
        titel = re.split(r"\s{2,}", (slot["titel"] or "").strip())[0]
        return f"{slot['dag']} {slot['start']} {titel}"

    # ---- 1. organisatoren ----
    for o in sorted(d["org_slots"], key=lambda r: slots[r["slot_id"]]["volgorde"]):
        slot = slots[o["slot_id"]]
        for pid in d["org_leden"].get(o["org_id"], []):
            if not is_vrij(slot["id"], pid):
                if bezet.get((slot["id"], pid)) == "#":
                    melding("info", f"{naam[pid]} organiseert {o['org_naam']} maar staat in de "
                                    f"planning als afwezig ({omschrijf(slot)}).")
                continue
            st = status_van(pid, slot)
            if st == "ja":
                toewijzen(slot["id"], pid, o["rol_code"], f"organisator {o['org_naam']}")
            elif st == "misschien":
                toewijzen(slot["id"], pid, o["rol_code"], f"organisator {o['org_naam']}", onzeker=True)
                melding("info", f"{naam[pid]} organiseert {o['org_naam']} maar heeft "
                                f"'misschien' aangegeven voor {slot['dag']} {slot['dagdeel']}.")
            elif st == "nee":
                melding("tekort", f"{naam[pid]} organiseert {o['org_naam']} maar is "
                                  f"{slot['dag']} {slot['dagdeel']} niet aanwezig.")
            else:
                melding("tekort", f"{naam[pid]} organiseert {o['org_naam']} maar heeft de "
                                  f"aanwezigheid voor {slot['dag']} {slot['dagdeel']} nog niet ingevuld.")

    # ---- 2. slapen en opstaan, per speltak ----
    per_slot = defaultdict(list)
    for e in d["eisen"]:
        per_slot[e["slot_id"]].append(e)

    for sid in volgorde:
        reqs = per_slot.get(sid)
        if not reqs:
            continue
        slot = slots[sid]

        def kandidaten(e):
            return [p for p in d["speltak_leden"].get(e["speltak_id"], [])
                    if is_vrij(sid, p) and status_van(p, slot) in ("ja", "misschien")]

        # eerst de speltak met de minste kandidaten, zodat iemand die bij
        # meerdere speltakken zit niet bij een ruim bezette speltak wordt 'opgebruikt'
        reqs = sorted(reqs, key=lambda e: len(kandidaten(e)) /
                      max(1, d["speltakken"][e["speltak_id"]]["min_leiding"]))
        gebruikt = set()

        for e in reqs:
            sp = d["speltakken"][e["speltak_id"]]
            leden = d["speltak_leden"].get(e["speltak_id"], [])
            code = e["rol_code"]
            min_leiding = sp["min_leiding"]
            gelijk = GELIJK.get(code, {code})

            al = [p for p in leden if bezet.get((sid, p)) in gelijk and p not in gebruikt][:min_leiding]
            gebruikt.update(al)
            nodig = min_leiding - len(al)
            aantal = len(al)

            if nodig > 0:
                sleutel = lambda p: (teller[(p, _groep(code))], totaal[p], _lot(sid, p), naam[p])
                cands = [p for p in kandidaten(e) if p not in gebruikt]
                ja = sorted([p for p in cands if status_van(p, slot) == "ja"], key=sleutel)
                mis = sorted([p for p in cands if status_van(p, slot) == "misschien"], key=sleutel)
                for p in ja[:nodig]:
                    toewijzen(sid, p, code, f"{sp['naam']}")
                    gebruikt.add(p); aantal += 1
                nodig -= len(ja[:nodig])
                for p in mis[:nodig]:
                    toewijzen(sid, p, code, f"{sp['naam']}", onzeker=True)
                    gebruikt.add(p); aantal += 1
                    melding("info", f"{naam[p]} ('misschien') is nodig voor {sp['naam']} bij {omschrijf(slot)}.")
                nodig -= len(mis[:nodig])

            if nodig > 0:
                vrij = [p for p in leden if is_vrij(sid, p)]
                nee = [p for p in vrij if status_van(p, slot) == "nee"]
                zonder = [p for p in vrij if status_van(p, slot) is None]
                bezig = [p for p in leden if not is_vrij(sid, p) and p not in gebruikt]
                if not leden:
                    reden = "er is geen leiding aan deze speltak gekoppeld"
                else:
                    reden = (f"{len(leden)} leiding gekoppeld: {len(nee)} niet aanwezig, "
                             f"{len(zonder)} nog niet ingevuld, "
                             f"{len(bezig)} al ingedeeld voor iets anders of afwezig in de planning")
                melding("tekort", f"{omschrijf(slot)}: {sp['naam']} heeft {aantal} van "
                                  f"{min_leiding} leiding ({reason}).".replace("{reason}", reden)
                        if False else
                        f"{omschrijf(slot)}: {sp['naam']} heeft {aantal} van "
                        f"{min_leiding} leiding ({reden}).")

    # ---- 3. algemene behoefte per slot (bijv. opbouw: 4 personen met rolcode OB) ----
    for b in sorted(d.get("behoeften", []), key=lambda r: slots[r["slot_id"]]["volgorde"]):
        slot = slots[b["slot_id"]]
        sid, code = slot["id"], b["rol_code"]
        gelijk = GELIJK.get(code, {code})
        al = ([p for (s, p), c in bezet.items() if s == sid and c in gelijk] +
              [p for (s, p), t in nieuw.items() if s == sid and t["code"] in gelijk])
        nodig = b["aantal"] - len(al)
        if nodig <= 0:
            continue

        sleutel = lambda p: (teller[(p, _groep(code))], totaal[p], _lot(sid, p), naam[p])
        vrij = [p for p in naam if is_vrij(sid, p)]
        ja = sorted([p for p in vrij if status_van(p, slot) == "ja"], key=sleutel)[:nodig]
        for p in ja:
            toewijzen(sid, p, code, f"nodig: {b['aantal']}x {code}")
        nodig -= len(ja)

        mis = sorted([p for p in vrij if status_van(p, slot) == "misschien" and is_vrij(sid, p)],
                     key=sleutel)[:nodig]
        for p in mis:
            toewijzen(sid, p, code, f"nodig: {b['aantal']}x {code}", onzeker=True)
            melding("info", f"{naam[p]} ('misschien') is nodig voor {code} bij {omschrijf(slot)}.")
        nodig -= len(mis)

        if nodig > 0:
            nee = [p for p in vrij if status_van(p, slot) == "nee"]
            zonder = [p for p in vrij if status_van(p, slot) is None]
            melding("tekort", f"{omschrijf(slot)}: {code} heeft {b['aantal'] - nodig} van "
                              f"{b['aantal']} personen ({len(nee)} niet aanwezig, "
                              f"{len(zonder)} nog niet ingevuld).")

    toewijzingen = sorted(nieuw.values(),
                          key=lambda t: (t["slot"]["volgorde"], t["reden"], t["naam"]))
    meldingen.sort(key=lambda m: (m["niveau"] != "tekort", m["tekst"]))
    return toewijzingen, meldingen

def maak_overzicht(d, toewijzingen):
    """Per persoon: wat is ingevuld, wat staat er al, wat wordt voorgesteld en waarom (niet).
    Geeft een lijst dicts; wie niets krijgt voorgesteld staat bovenaan, met een reden."""
    dagdelen = d.get("dagdelen") or sorted({(s["dag"], s["dagdeel"]) for s in d["slots"]})
    speltak_van = defaultdict(list)
    for sid, leden in d["speltak_leden"].items():
        for p in leden:
            speltak_van[p].append(d["speltakken"][sid]["naam"])
    n_org = Counter()
    for leden in d["org_leden"].values():
        for p in leden:
            n_org[p] += 1
    handmatig = Counter(p for (s, p), c in d["bestaand"].items() if c not in ("#", "?"))
    voorgesteld = Counter(t["person_id"] for t in toewijzingen)

    rijen = []
    for pid, naam in d["personen"].items():
        tel = Counter(d["status"].get((pid, dag, dd)) for dag, dd in dagdelen)
        ja, mis, nee = tel["ja"], tel["misschien"], tel["nee"]
        leeg = len(dagdelen) - ja - mis - nee
        reden = ""
        if voorgesteld[pid] == 0:
            if ja == 0 and mis == 0:
                reden = ("Nog geen aanwezigheid ingevuld." if nee == 0
                         else "Overal 'nee' ingevuld.")
            elif ja == 0:
                reden = "Alleen 'misschien' ingevuld: die worden alleen bij een tekort ingedeeld."
            elif not speltak_van[pid] and not n_org[pid]:
                reden = ("Geen speltak of activiteit gekoppeld, en er was geen 'nodig'-taak "
                         "(zoals opbouw) die nog open stond.")
            else:
                reden = "Er stond niets meer open waarvoor deze persoon in aanmerking kwam."
        rijen.append({"naam": naam, "speltak": ", ".join(speltak_van[pid]), "n_org": n_org[pid],
                      "ja": ja, "misschien": mis, "nee": nee, "leeg": leeg,
                      "totaal": len(dagdelen), "handmatig": handmatig[pid],
                      "voorgesteld": voorgesteld[pid], "reden": reden})
    rijen.sort(key=lambda r: (r["reden"] == "", r["naam"]))
    return rijen