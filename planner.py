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
from collections import Counter, defaultdict

# Rolcodes die voor het tellen als hetzelfde gelden
GELIJK = {"K": {"K", "K*"}, "K*": {"K", "K*"}}


def _groep(code):
    return "K" if code in ("K", "K*") else code


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
                sleutel = lambda p: (teller[(p, _groep(code))], totaal[p], naam[p])
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

    toewijzingen = sorted(nieuw.values(),
                          key=lambda t: (t["slot"]["volgorde"], t["reden"], t["naam"]))
    meldingen.sort(key=lambda m: (m["niveau"] != "tekort", m["tekst"]))
    return toewijzingen, meldingen