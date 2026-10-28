"""Excel-sjabloon en -import voor aanwezigheid per dagdeel.

Het sjabloon heeft een rij per persoon en een kolom per dagdeel
(bijv. 'Vrijdag middag'), al ingevuld met wat er nu in de app staat.
Bij het importeren geldt: een lege cel laat de bestaande keuze ongemoeid.
"""
import io
import re

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BLADNAAM = "Aanwezigheid"
MAX_RIJEN = 1000

ALS_JA = {"ja", "j", "yes", "y", "x", "1", "✓", "✔", "aanwezig", "true", "waar"}
ALS_NEE = {"nee", "n", "no", "0", "afwezig", "#", "false", "onwaar"}
ALS_MISSCHIEN = {"misschien", "m", "?", "onzeker", "eventueel", "evt"}


def _norm(tekst):
    return re.sub(r"\s+", " ", str(tekst if tekst is not None else "")).strip().casefold()


def kolomkop(dag, dagdeel):
    return f"{dag} {dagdeel}"


def maak_sjabloon(personen, dagdelen, bestaand):
    """personen = [(id, naam)], dagdelen = [(dag, dagdeel)],
    bestaand = {(person_id, dag, dagdeel): status}. Geeft de .xlsx als bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = BLADNAAM

    koppen = ["Naam"] + [kolomkop(d, dd) for d, dd in dagdelen]
    ws.append(koppen)
    for pid, naam in personen:
        ws.append([naam] + [bestaand.get((pid, d, dd), None) for d, dd in dagdelen])

    kop_stijl = PatternFill("solid", start_color="FF1F6F3D")
    for cel in ws[1]:
        cel.font = Font(bold=True, color="FFFFFFFF")
        cel.fill = kop_stijl
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32
    ws.column_dimensions["A"].width = 26
    for i in range(2, len(koppen) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 15
        for rij in range(2, len(personen) + 2):
            ws.cell(row=rij, column=i).alignment = Alignment(horizontal="center")
    ws.freeze_panes = "B2"

    if personen and dagdelen:
        keuze = DataValidation(type="list", formula1='"ja,nee,misschien"', allow_blank=True,
                               showErrorMessage=True, errorTitle="Ongeldige keuze",
                               error="Kies ja, nee of misschien (of laat leeg).")
        ws.add_data_validation(keuze)
        keuze.add(f"B2:{get_column_letter(len(koppen))}{len(personen) + 1}")

    uitleg = wb.create_sheet("Uitleg")
    regels = [
        "Zo vul je dit bestand in",
        "",
        "• Eén rij per persoon, één kolom per dagdeel.",
        "• Vul per cel in: ja, nee of misschien.",
        "• Een lege cel betekent: niets wijzigen. Er wordt dus niets gewist.",
        "• Pas de namen in kolom A en de koppen in rij 1 niet aan. Ze worden gebruikt om",
        "  personen en dagdelen te herkennen.",
        "• Ook geaccepteerd: j, y, x, 1 (= ja); n, 0, # (= nee); m, ? (= misschien).",
        "• Sla het bestand op als .xlsx en upload het onder Beheer → Aanwezigheid importeren.",
    ]
    for r in regels:
        uitleg.append([r])
    uitleg["A1"].font = Font(bold=True, size=14)
    uitleg.column_dimensions["A"].width = 95

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _waarde_naar_status(waarde):
    """Geeft 'ja'/'nee'/'misschien', None voor leeg, of False voor onbekend."""
    if waarde is None:
        return None
    if isinstance(waarde, bool):
        return "ja" if waarde else "nee"
    if isinstance(waarde, float) and waarde == int(waarde):
        waarde = int(waarde)
    tekst = _norm(waarde)
    if tekst == "":
        return None
    if tekst in ALS_JA:
        return "ja"
    if tekst in ALS_NEE:
        return "nee"
    if tekst in ALS_MISSCHIEN:
        return "misschien"
    return False


def lees_aanwezigheid(inhoud, personen, dagdelen, bestaand):
    """Leest een ingevuld sjabloon. Geeft een dict met:
       records      [(person_id, dag, dagdeel, status)]  om op te slaan
       wijzigingen  lijst voor het voorbeeld (alleen nieuw/gewijzigd)
       meldingen    [{'niveau': 'fout'|'info', 'tekst': ...}]
       n_personen, n_nieuw, n_gewijzigd, n_gelijk
    Gooit ValueError bij een onbruikbaar bestand."""
    try:
        wb = load_workbook(io.BytesIO(inhoud), read_only=True, data_only=True)
    except Exception:
        raise ValueError("Dit bestand kon niet worden gelezen. Upload een .xlsx-bestand.")

    ws = wb[BLADNAAM] if BLADNAAM in wb.sheetnames else wb.worksheets[0]
    rijen = ws.iter_rows(values_only=True, max_row=MAX_RIJEN + 1)
    try:
        kop = next(rijen)
    except StopIteration:
        raise ValueError("Het bestand is leeg.")

    label_naar_dagdeel = {_norm(kolomkop(d, dd)): (d, dd) for d, dd in dagdelen}
    naam_kolom, kolommen, meldingen = None, {}, []
    for i, k in enumerate(kop):
        n = _norm(k)
        if n == "":
            continue
        if n == "naam" and naam_kolom is None:
            naam_kolom = i
        elif n in label_naar_dagdeel:
            kolommen[i] = label_naar_dagdeel[n]
        else:
            meldingen.append({"niveau": "info",
                              "tekst": f"Kolom '{k}' is niet herkend en wordt overgeslagen."})
    if naam_kolom is None:
        raise ValueError("De kolom 'Naam' ontbreekt in de eerste rij.")
    if not kolommen:
        raise ValueError("Geen enkele kolom met een dagdeel is herkend. "
                         "Gebruik het sjabloon (kopjes zoals 'Vrijdag middag').")
    ontbrekend = [kolomkop(d, dd) for d, dd in dagdelen if (d, dd) not in kolommen.values()]
    if ontbrekend:
        meldingen.append({"niveau": "info",
                          "tekst": "Niet in het bestand, dus ongewijzigd: " + ", ".join(ontbrekend) + "."})

    per_naam = {}
    for pid, naam in personen:
        per_naam.setdefault(_norm(naam), []).append((pid, naam))

    resultaat = {}                       # person_id -> {(dag, dagdeel): status}
    gezien = {}
    namen_uit_bestand = {}
    for rijnr, rij in enumerate(rijen, start=2):
        if rij is None or naam_kolom >= len(rij):
            continue
        ruwe_naam = rij[naam_kolom]
        if _norm(ruwe_naam) == "":
            continue
        kandidaten = per_naam.get(_norm(ruwe_naam), [])
        if not kandidaten:
            meldingen.append({"niveau": "fout",
                              "tekst": f"Rij {rijnr}: de naam '{ruwe_naam}' staat niet in de app "
                                       f"en wordt overgeslagen."})
            continue
        if len(kandidaten) > 1:
            meldingen.append({"niveau": "fout",
                              "tekst": f"Rij {rijnr}: de naam '{ruwe_naam}' is niet eenduidig "
                                       f"en wordt overgeslagen."})
            continue
        pid, naam = kandidaten[0]
        namen_uit_bestand[pid] = naam
        if pid in gezien:
            meldingen.append({"niveau": "info",
                              "tekst": f"{naam} staat meerdere keren in het bestand "
                                       f"(rij {gezien[pid]} en {rijnr}). De laatste rij telt."})
            resultaat[pid] = {}
        gezien[pid] = rijnr
        resultaat.setdefault(pid, {})
        for i, (d, dd) in kolommen.items():
            waarde = rij[i] if i < len(rij) else None
            status = _waarde_naar_status(waarde)
            if status is None:
                continue
            if status is False:
                meldingen.append({"niveau": "fout",
                                  "tekst": f"Rij {rijnr}, {naam}, {kolomkop(d, dd)}: "
                                           f"'{waarde}' is geen ja, nee of misschien. Overgeslagen."})
                continue
            resultaat[pid][(d, dd)] = status
    wb.close()

    records, wijzigingen = [], []
    n_nieuw = n_gewijzigd = n_gelijk = 0
    for pid, cellen in resultaat.items():
        for (d, dd), status in cellen.items():
            oud = bestaand.get((pid, d, dd))
            if oud == status:
                n_gelijk += 1
                continue
            if oud is None:
                n_nieuw += 1
            else:
                n_gewijzigd += 1
            records.append((pid, d, dd, status))
            wijzigingen.append({"naam": namen_uit_bestand[pid], "dagdeel": kolomkop(d, dd),
                                "oud": oud, "nieuw": status})

    return {"records": records, "wijzigingen": wijzigingen, "meldingen": meldingen,
            "n_personen": len(resultaat), "n_nieuw": n_nieuw,
            "n_gewijzigd": n_gewijzigd, "n_gelijk": n_gelijk}