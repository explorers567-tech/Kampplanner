import io
import os
import re
import secrets
import time
import uuid
from datetime import timedelta
from functools import wraps

from flask import (Flask, render_template, abort, request, redirect, url_for,
                   flash, send_file, send_from_directory, session, g)
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

import db
import excel_aanwezigheid
import icons
import planner

app = Flask(__name__)

# Geheime sleutel: eenmalig aangemaakt en bewaard in een bestand naast app.py
sleutel_pad = os.path.join(app.root_path, "secret_key.txt")
if not os.path.exists(sleutel_pad):
    with open(sleutel_pad, "w") as f:
        f.write(secrets.token_hex(32))
with open(sleutel_pad) as f:
    app.config["SECRET_KEY"] = f.read().strip()

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024        # max 10 MB
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)

UPLOAD_MAP = os.path.join(app.root_path, "uploads")
TOEGESTAAN = {"pdf", "png", "jpg", "jpeg", "docx"}
STATUSSEN = {"", "ja", "nee", "misschien"}


# ---------- beveiliging ----------

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def is_admin():
    return session.get("admin_tot", 0) > time.time()


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["is_admin"] = is_admin


@app.before_request
def controleer_csrf():
    if request.method == "POST":
        verstuurd = request.form.get("csrf", "").encode()
        verwacht = session.get("csrf", "").encode()
        if not verwacht or not secrets.compare_digest(verstuurd, verwacht):
            abort(400)


def inloggen_vereist(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not (session.get("person_id") or is_admin()):
            return render_template("geen_toegang.html"), 403
        return f(*args, **kwargs)
    return inner


def admin_vereist(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return inner


def verwijder_bestand(opslag_naam):
    pad = os.path.join(UPLOAD_MAP, os.path.basename(opslag_naam))
    if os.path.exists(pad):
        os.remove(pad)


# ---------- inloggen met persoonlijke link ----------

@app.route("/p/<token>")
def inloggen_token(token):
    persoon = db.vind_persoon_op_token(token)
    if persoon is None:
        abort(404)
    session.permanent = True
    session["person_id"] = persoon["id"]
    return redirect(url_for("persoonlijk"))      # de token verdwijnt zo uit de adresbalk


# ---------- pagina's voor leiding ----------

@app.route("/")
@inloggen_vereist
def overzicht():
    return render_template("overzicht.html", rijen=db.haal_telling())


@app.route("/schema")
@inloggen_vereist
def schema():
    soort = request.args.get("soort")
    if soort not in db.SOORTEN:
        soort = None
    slots, personen, cellen = db.haal_schema(soort)
    return render_template("schema.html", slots=slots, personen=personen, cellen=cellen,
                           soort=soort, soorten=db.haal_soorten_met_slots(),
                           soortnamen=db.SOORTEN)


@app.route("/mijn")
@inloggen_vereist
def persoonlijk():
    person_id = session.get("person_id")
    if not person_id:                      # beheerder zonder eigen persoon
        return redirect(url_for("admin"))
    persoon, rijen = db.haal_persoonlijk(person_id)
    if persoon is None:
        session.pop("person_id", None)     # persoon bestaat niet meer
        abort(404)
    return render_template("persoonlijk.html", persoon=persoon, rijen=rijen)

def verwerk_invoer(person_id, terug_url, admin_modus):
    persoon, dagdelen, uploads = db.haal_beschikbaarheid(person_id)
    if persoon is None:
        abort(404)

    if request.method == "POST":
        bestand = request.files.get("document")
        opslag_naam = None
        if bestand and bestand.filename:
            ext = bestand.filename.rsplit(".", 1)[-1].lower() if "." in bestand.filename else ""
            if ext not in TOEGESTAAN:
                flash("Dit bestandstype is niet toegestaan "
                      "(pdf, png, jpg, jpeg of docx).", "danger")
                return redirect(terug_url)
            opslag_naam = f"{uuid.uuid4().hex}.{ext}"

        ingevuld = []
        for d in dagdelen:
            status = request.form.get(d["veld"], "")
            if status in STATUSSEN:
                ingevuld.append((d["dag"], d["dagdeel"], status))
        db.sla_beschikbaarheid_op(person_id, ingevuld)

        if opslag_naam:
            os.makedirs(UPLOAD_MAP, exist_ok=True)
            bestand.save(os.path.join(UPLOAD_MAP, opslag_naam))
            originele_naam = secure_filename(bestand.filename) or "document"
            db.sla_upload_op(person_id, originele_naam, opslag_naam)

        flash("Opgeslagen!", "success")
        return redirect(terug_url)

    return render_template("invoer.html", persoon=persoon, dagdelen=dagdelen,
                           uploads=uploads, admin_modus=admin_modus)

@app.route("/invoer", methods=["GET", "POST"])
def invoer():
    person_id = session.get("person_id")
    if not person_id:
        return render_template("geen_toegang.html"), 403
    return verwerk_invoer(person_id, url_for("invoer"), admin_modus=False)


@app.route("/upload/<int:upload_id>")
def download(upload_id):
    u = db.haal_upload(upload_id)
    # 404 in plaats van 403: zo verraad je niet dat het bestand bestaat
    if u is None or not (is_admin() or session.get("person_id") == u["person_id"]):
        abort(404)
    return send_from_directory(UPLOAD_MAP, u["opslag_naam"],
                               as_attachment=True, download_name=u["originele_naam"])


# ---------- beheer ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin = db.vind_admin(request.form.get("gebruikersnaam", "").strip())
        wachtwoord = request.form.get("wachtwoord", "")
        if admin and check_password_hash(admin["wachtwoord_hash"], wachtwoord):
            session.permanent = True
            session["admin_tot"] = time.time() + 8 * 3600     # 8 uur ingelogd
            return redirect(url_for("admin"))
        flash("Onjuiste gebruikersnaam of wachtwoord.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_tot", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_vereist
def admin():
    return render_template("admin.html", personen=db.haal_personen_beheer())


@app.route("/admin/persoon/toevoegen", methods=["POST"])
@admin_vereist
def admin_toevoegen():
    naam = request.form.get("naam", "").strip()
    if not naam:
        flash("Vul een naam in.", "danger")
    else:
        try:
            db.voeg_persoon_toe(naam, 1 if request.form.get("is_ouderraad") else 0)
            flash(f"{naam} is toegevoegd.", "success")
        except ValueError as fout:
            flash(str(fout), "danger")
    return redirect(url_for("admin"))


@app.route("/admin/persoon/<int:person_id>/wijzig", methods=["POST"])
@admin_vereist
def admin_wijzig(person_id):
    naam = request.form.get("naam", "").strip()
    if not naam:
        flash("De naam mag niet leeg zijn.", "danger")
    else:
        try:
            db.wijzig_persoon(person_id, naam, 1 if request.form.get("is_ouderraad") else 0)
            flash("Persoon bijgewerkt.", "success")
        except ValueError as fout:
            flash(str(fout), "danger")
    return redirect(url_for("admin"))

@app.route("/admin/persoon/<int:person_id>/token", methods=["POST"])
@admin_vereist
def admin_nieuw_token(person_id):
    db.nieuw_token(person_id)
    flash("Nieuwe link aangemaakt. De oude link werkt niet meer.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/persoon/<int:person_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_verwijder(person_id):
    for opslag_naam in db.verwijder_persoon(person_id):
        verwijder_bestand(opslag_naam)
    flash("Persoon en bijbehorende gegevens zijn verwijderd.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/persoon/<int:person_id>/profiel", methods=["GET", "POST"])
@admin_vereist

def admin_profiel(person_id):
    persoon, speltakken, organisaties = db.haal_persoon_profiel(person_id)
    if persoon is None:
        abort(404)

    if request.method == "POST":
        geldige_speltakken = db.geldige_speltak_ids()
        speltak_ids = [int(x) for x in request.form.getlist("speltak")
                       if x.isdigit() and int(x) in geldige_speltakken]
        geldige_orgs = db.geldige_organisatie_ids()
        org_ids = [int(x) for x in request.form.getlist("organisatie")
                   if x.isdigit() and int(x) in geldige_orgs]

        db.sla_persoon_profiel_op(person_id, speltak_ids, org_ids)
        flash("Profiel opgeslagen.", "success")
        return redirect(url_for("admin_profiel", person_id=person_id))

    return render_template("admin_profiel.html", persoon=persoon,
                           speltakken=speltakken, organisaties=organisaties)

@app.route("/admin/invoer/<int:person_id>", methods=["GET", "POST"])
@admin_vereist
def admin_invoer(person_id):
    return verwerk_invoer(person_id,
                          url_for("admin_invoer", person_id=person_id),
                          admin_modus=True)


@app.route("/admin/upload/<int:upload_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_upload_verwijder(upload_id):
    rij = db.verwijder_upload(upload_id)
    if rij is None:
        abort(404)
    verwijder_bestand(rij["opslag_naam"])
    flash("Bestand verwijderd.", "success")
    return redirect(url_for("admin_invoer", person_id=rij["person_id"]))

@app.route("/admin/planning")
@admin_vereist
def admin_planning():
    return render_template("planning_overzicht.html", slots=db.haal_planning_slots())


@app.route("/admin/planning/<int:slot_id>", methods=["GET", "POST"])
@admin_vereist
def admin_planning_slot(slot_id):
    slot, rijen = db.haal_slot_planning(slot_id)
    if slot is None:
        abort(404)

    opties = dict(db.haal_rolopties())
    for r in rijen:        # codes die al in de planning staan maar niet in roles
        if r["code"] and r["code"] not in opties:
            opties[r["code"]] = "(niet in rollenlijst)"

    if request.method == "POST":
        keuzes = []
        for r in rijen:
            code = request.form.get(f"p_{r['id']}", "")
            if code == "" or code in opties:
                keuzes.append((r["id"], code))
        db.sla_planning_op(slot_id, keuzes)
        flash("Planning opgeslagen.", "success")
        return redirect(url_for("admin_planning_slot", slot_id=slot_id))

    return render_template("planning_slot.html", slot=slot, rijen=rijen, opties=opties)

# ---------- beheer: activiteiten (borrel, opening, diner, spellen ...) ----------

def rolopties_zonder_afwezig():
    opties = dict(db.haal_rolopties())
    opties.pop("#", None)
    opties.pop("?", None)
    return opties


@app.route("/admin/activiteiten", methods=["GET", "POST"])
@admin_vereist
def admin_activiteiten():
    if request.method == "POST":
        naam = request.form.get("naam", "").strip()
        if not naam:
            flash("Vul een naam in.", "danger")
        else:
            try:
                org_id = db.maak_organisatie(naam)
                return redirect(url_for("admin_activiteit", org_id=org_id))
            except ValueError as fout:
                flash(str(fout), "danger")
        return redirect(url_for("admin_activiteiten"))
    return render_template("organisaties.html", organisaties=db.haal_organisaties())

@app.route("/admin/activiteiten/<int:org_id>", methods=["GET", "POST"])
@admin_vereist
def admin_activiteit(org_id):
    org, slots, personen = db.haal_organisatie(org_id)
    if org is None:
        abort(404)

    opties = rolopties_zonder_afwezig()
    for s in slots:
        if s["rol_code"] and s["rol_code"] not in opties:
            opties[s["rol_code"]] = "(niet in rollenlijst)"

    if request.method == "POST":
        naam = request.form.get("naam", "").strip()
        if not naam:
            flash("De naam mag niet leeg zijn.", "danger")
            return redirect(url_for("admin_activiteit", org_id=org_id))

        slot_codes = []
        for s in slots:
            code = request.form.get(f"slot_{s['id']}", "")
            if code and code in opties:
                slot_codes.append((s["id"], code))

        behoeften, fouten = {}, []
        for s in slots:
            tekst = request.form.get(f"nodig_{s['id']}")
            if tekst is None:               # veld stond niet in het formulier: niet aanraken
                continue
            lijst, fout = lees_behoefte(tekst, rolopties_zonder_afwezig())
            if fout:
                titel = re.split(r"\s{2,}", (s["titel"] or "").strip())[0]
                fouten.append(f"{s['dag']} {s['start']} {titel}: {fout}")
            else:
                behoeften[s["id"]] = lijst
        if fouten:
            for f in fouten:
                flash(f, "danger")
            flash("Er is niets opgeslagen. Verbeter de regels hierboven en probeer opnieuw.", "warning")
            return redirect(url_for("admin_activiteit", org_id=org_id))

        geldige_personen = db.haal_persoon_ids()
        person_ids = [int(x) for x in request.form.getlist("persoon")
                      if x.isdigit() and int(x) in geldige_personen]
        try:
            db.sla_organisatie_op(org_id, naam, slot_codes, person_ids, behoeften)
            flash("Activiteit opgeslagen.", "success")
        except ValueError as fout:
            flash(str(fout), "danger")
        return redirect(url_for("admin_activiteit", org_id=org_id))

    return render_template("organisatie.html", org=org, slots=slots,
                           personen=personen, opties=opties)

@app.route("/admin/activiteiten/<int:org_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_activiteit_verwijder(org_id):
    db.verwijder_organisatie(org_id)
    flash("Activiteit verwijderd.", "success")
    return redirect(url_for("admin_activiteiten"))


# ---------- beheer: regels voor slapen en opstaan ----------

@app.route("/admin/eisen", methods=["GET", "POST"])
@admin_vereist
def admin_eisen():
    slots, speltakken, eisen, codes = db.haal_eisen_matrix()
    opties = rolopties_zonder_afwezig()

    if request.method == "POST":
        nieuwe, fouten = [], 0
        for s in slots:
            gekozen = [sp["id"] for sp in speltakken
                       if request.form.get(f"e_{s['id']}_{sp['id']}")]
            if not gekozen:
                continue
            code = request.form.get(f"code_{s['id']}", "")
            if code not in opties:
                fouten += 1
                continue
            for speltak_id in gekozen:
                nieuwe.append((s["id"], speltak_id, code))
        if fouten:
            flash(f"{fouten} slot(s) hebben een speltak maar geen geldige rolcode. "
                  "Er is niets opgeslagen.", "danger")
        else:
            db.sla_eisen_op(nieuwe)
            flash("Regels opgeslagen.", "success")
        return redirect(url_for("admin_eisen"))

    return render_template("eisen.html", slots=slots, speltakken=speltakken,
                           eisen=eisen, codes=codes, opties=opties)


# ---------- beheer: automatische indeling ----------

@app.route("/admin/auto", methods=["GET", "POST"])
@admin_vereist
def admin_auto():
    if request.method == "POST":
        actie = request.form.get("actie")
        if actie == "toepassen":
            toewijzingen, meldingen = planner.maak_planning(db.haal_planner_data())
            db.bewaar_auto_planning(toewijzingen)
            flash(f"{len(toewijzingen)} toewijzingen opgeslagen. "
                  "Handmatige toewijzingen zijn niet aangepast.", "success")
        elif actie == "wissen":
            n = db.wis_auto_planning()
            flash(f"{n} automatische toewijzingen verwijderd.", "success")
        return redirect(url_for("admin_auto"))

    toewijzingen, meldingen = planner.maak_planning(db.haal_planner_data())
    return render_template("auto.html", toewijzingen=toewijzingen, meldingen=meldingen,
                           n_auto=db.tel_auto_planning())

# ---------- pictogrammen bij rolcodes ----------

def _rol_omschrijvingen():
    if "rol_omschrijvingen" not in g:           # per aanvraag maar één keer ophalen
        g.rol_omschrijvingen = db.haal_rolopties()
    return g.rol_omschrijvingen


@app.template_global("rol")
def rol(code):
    """Toont het pictogram van een rolcode, met de omschrijving als tooltip.
    Onbekende codes worden gewoon als tekst getoond."""
    code = str(code or "").strip()
    if not code:
        return ""
    icoon = icons.ICONEN.get(code)
    if not icoon:
        return Markup(escape(code))
    uitleg = escape(_rol_omschrijvingen().get(code, code))
    return Markup(f'<span class="rol" title="{uitleg}" aria-label="{uitleg}">{escape(icoon)}</span>')


@app.template_global("rol_legenda")
def rol_legenda():
    return [{"code": c, "icoon": icons.ICONEN.get(c, ""), "omschrijving": o}
            for c, o in _rol_omschrijvingen().items()]


# ---------- beheer: aanwezigheid importeren uit Excel ----------

IMPORT_MAP = os.path.join(app.root_path, "import_tmp")


def ruim_import_op():
    """Verwijdert tijdelijke uploads ouder dan een dag."""
    if os.path.isdir(IMPORT_MAP):
        grens = time.time() - 24 * 3600
        for naam in os.listdir(IMPORT_MAP):
            pad = os.path.join(IMPORT_MAP, naam)
            if os.path.isfile(pad) and os.path.getmtime(pad) < grens:
                os.remove(pad)


@app.route("/admin/import/sjabloon")
@admin_vereist
def admin_import_sjabloon():
    inhoud = excel_aanwezigheid.maak_sjabloon(
        db.haal_personen_kort(), db.haal_dagdelen(), db.haal_alle_aanwezigheid())
    return send_file(io.BytesIO(inhoud), as_attachment=True, download_name="aanwezigheid.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/admin/import", methods=["GET", "POST"])
@admin_vereist
def admin_import():
    if request.method == "POST":
        actie = request.form.get("actie")

        if actie == "controleren":
            bestand = request.files.get("bestand")
            if not bestand or not bestand.filename:
                flash("Kies eerst een bestand.", "danger")
                return redirect(url_for("admin_import"))
            if not bestand.filename.lower().endswith(".xlsx"):
                flash("Upload een .xlsx-bestand (Excel).", "danger")
                return redirect(url_for("admin_import"))
            inhoud = bestand.read()
            try:
                uitkomst = excel_aanwezigheid.lees_aanwezigheid(
                    inhoud, db.haal_personen_kort(), db.haal_dagdelen(),
                    db.haal_alle_aanwezigheid())
            except ValueError as fout:
                flash(str(fout), "danger")
                return redirect(url_for("admin_import"))
            ruim_import_op()
            os.makedirs(IMPORT_MAP, exist_ok=True)
            sleutel = uuid.uuid4().hex
            with open(os.path.join(IMPORT_MAP, sleutel + ".xlsx"), "wb") as f:
                f.write(inhoud)
            return render_template("import_voorbeeld.html", uitkomst=uitkomst, sleutel=sleutel)

        if actie == "toepassen":
            sleutel = request.form.get("sleutel", "")
            if not re.fullmatch(r"[0-9a-f]{32}", sleutel):
                abort(400)
            pad = os.path.join(IMPORT_MAP, sleutel + ".xlsx")
            if not os.path.exists(pad):
                flash("De upload is verlopen. Begin opnieuw.", "danger")
                return redirect(url_for("admin_import"))
            with open(pad, "rb") as f:
                inhoud = f.read()
            try:
                uitkomst = excel_aanwezigheid.lees_aanwezigheid(
                    inhoud, db.haal_personen_kort(), db.haal_dagdelen(),
                    db.haal_alle_aanwezigheid())
            except ValueError as fout:
                flash(str(fout), "danger")
                return redirect(url_for("admin_import"))
            db.sla_aanwezigheid_import(uitkomst["records"])
            os.remove(pad)
            flash(f"{len(uitkomst['records'])} aanwezigheden opgeslagen "
                  f"({uitkomst['n_nieuw']} nieuw, {uitkomst['n_gewijzigd']} gewijzigd).", "success")
            return redirect(url_for("admin"))

        abort(400)

    return render_template("import.html")

# ---------- beheer: dagen en slots ----------

@app.route("/admin/dagen", methods=["GET", "POST"])
@admin_vereist
def admin_dagen():
    if request.method == "POST":
        naam = request.form.get("naam", "").strip()
        soort = request.form.get("soort", "")
        voor = request.form.get("voor", "")
        if not naam or len(naam) > 60:
            flash("Geef de dag een naam van maximaal 60 tekens.", "danger")
        elif soort not in db.SOORTEN:
            flash("Kies een soort dag.", "danger")
        else:
            try:
                dag_id = db.maak_dag(naam, soort, bool(request.form.get("heeft_nacht")),
                                     int(voor) if voor.isdigit() else None)
                flash(f"{naam} is toegevoegd. Voeg nu de slots toe.", "success")
                return redirect(url_for("admin_dag", dag_id=dag_id))
            except ValueError as fout:
                flash(str(fout), "danger")
        return redirect(url_for("admin_dagen"))
    return render_template("dagen.html", dagen=db.haal_dagen(), soorten=db.SOORTEN)


def lees_behoefte(tekst, opties):
    """Leest wat er nodig is, zoals '6 L, 2 OK' (of '6xL'). Geeft (lijst van (aantal, code), fout)."""
    codes = {c.upper(): c for c in opties}
    uit, gezien = [], set()
    for deel in re.split(r"[,;]", tekst):
        deel = deel.strip()
        if not deel:
            continue
        delen = deel.split()
        m = re.fullmatch(r"(\d{1,3})[x×](\S+)", deel)
        if len(delen) == 2 and delen[0].isdigit():
            aantal, codetekst = int(delen[0]), delen[1]
        elif m:
            aantal, codetekst = int(m.group(1)), m.group(2)
        else:
            return None, f"'{deel}' begrijp ik niet. Gebruik bijvoorbeeld '6 L'."
        code = codes.get(codetekst.upper())
        if code is None:
            return None, f"rolcode '{codetekst}' bestaat niet. Voeg die eerst toe onder Rollen."
        if aantal < 1:
            return None, f"'{deel}': het aantal moet minstens 1 zijn."
        if code in gezien:
            return None, f"rolcode {code} staat twee keer."
        gezien.add(code)
        uit.append((aantal, code))
    return uit, None


def lees_slotregels(tekst, opties):
    """Leest regels als '19:00 Tent opbouwen | 4 OB, 2 K'. Geeft (slots, fouten)."""
    slots, fouten = [], []
    for nr, ruw in enumerate(tekst.splitlines(), start=1):
        lijn = ruw.strip()
        if not lijn:
            continue
        behoeften = []
        if "|" in lijn:
            lijn, _, rest = lijn.rpartition("|")
            behoeften, fout = lees_behoefte(rest, opties)
            if fout:
                fouten.append(f"Regel {nr}: {fout}")
                continue
        m = re.fullmatch(r"(\d{1,2}):(\d{2})\s+(.+)", lijn.strip())
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            fouten.append(f"Regel {nr}: begin met een tijd zoals 19:00, gevolgd door de titel.")
            continue
        slots.append((f"{int(m.group(1)):02d}:{m.group(2)}", m.group(3).strip()[:120], behoeften))
    if not slots and not fouten:
        fouten.append("Er staat niets in het veld.")
    return slots, fouten


@app.route("/admin/dagen/<int:dag_id>", methods=["GET", "POST"])
@admin_vereist
def admin_dag(dag_id):
    dag, slots = db.haal_dag(dag_id)
    if dag is None:
        abort(404)
    opties = rolopties_zonder_afwezig()
    regels_tekst = ""

    if request.method == "POST":
        actie = request.form.get("actie")
        if actie == "dag_opslaan":
            naam = request.form.get("naam", "").strip()
            soort = request.form.get("soort", "")
            if not naam or len(naam) > 60 or soort not in db.SOORTEN:
                flash("Geef een naam (maximaal 60 tekens) en kies een soort.", "danger")
            else:
                try:
                    db.wijzig_dag(dag_id, naam, soort, bool(request.form.get("heeft_nacht")))
                    flash("Dag opgeslagen.", "success")
                except ValueError as fout:
                    flash(str(fout), "danger")
            return redirect(url_for("admin_dag", dag_id=dag_id))

        if actie == "slots_toevoegen":
            regels_tekst = request.form.get("regels", "")
            nieuwe, fouten = lees_slotregels(regels_tekst, opties)
            if fouten:
                for f in fouten:
                    flash(f, "danger")
                flash("Er is niets toegevoegd. Verbeter de regels en probeer opnieuw.", "warning")
            else:
                db.voeg_slots_toe(dag["naam"], nieuwe)
                flash(f"{len(nieuwe)} slot(s) toegevoegd.", "success")
                return redirect(url_for("admin_dag", dag_id=dag_id))
        else:
            abort(400)

    return render_template("dag.html", dag=dag, slots=slots, opties=opties,
                           soorten=db.SOORTEN, regels_tekst=regels_tekst)


@app.route("/admin/dagen/<int:dag_id>/verplaats", methods=["POST"])
@admin_vereist
def admin_dag_verplaats(dag_id):
    richting = request.form.get("richting")
    if richting in ("omhoog", "omlaag"):
        db.verplaats_dag(dag_id, richting)
    return redirect(url_for("admin_dagen"))


@app.route("/admin/dagen/<int:dag_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_dag_verwijder(dag_id):
    try:
        db.verwijder_dag(dag_id)
        flash("Dag verwijderd.", "success")
        return redirect(url_for("admin_dagen"))
    except ValueError as fout:
        flash(str(fout), "danger")
        return redirect(url_for("admin_dag", dag_id=dag_id))


@app.route("/admin/slots/<int:slot_id>/wijzig", methods=["POST"])
@admin_vereist
def admin_slot_wijzig(slot_id):
    slot = db.haal_slot(slot_id)
    if slot is None:
        abort(404)
    terug = url_for("admin_dag", dag_id=slot["dag_id"]) if slot["dag_id"] else url_for("admin_dagen")

    m = re.fullmatch(r"(\d{1,2}):(\d{2})", request.form.get("start", "").strip())
    titel = request.form.get("titel", "").strip()[:120]
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59 or not titel:
        flash("Vul een geldige tijd (zoals 19:00) en een titel in.", "danger")
        return redirect(terug)
    start = f"{int(m.group(1)):02d}:{m.group(2)}"

    behoefte = None
    aantal = request.form.get("b_aantal", "").strip()
    code = request.form.get("b_code", "")
    if aantal.isdigit() and int(aantal) > 0 and code:
        if code not in rolopties_zonder_afwezig():
            flash("Onbekende rolcode.", "danger")
            return redirect(terug)
        behoefte = (min(int(aantal), 999), code)

    db.wijzig_slot(slot_id, start, titel, behoefte)
    flash("Slot opgeslagen.", "success")
    return redirect(terug)


@app.route("/admin/slots/<int:slot_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_slot_verwijder(slot_id):
    slot = db.haal_slot(slot_id)
    if slot is None:
        abort(404)
    terug = url_for("admin_dag", dag_id=slot["dag_id"]) if slot["dag_id"] else url_for("admin_dagen")
    db.verwijder_slot(slot_id)
    flash("Slot verwijderd, met de bijbehorende toewijzingen.", "success")
    return redirect(terug)


# ---------- beheer: rollen (rolcodes) ----------

@app.route("/admin/rollen", methods=["GET", "POST"])
@admin_vereist
def admin_rollen():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        omschrijving = request.form.get("omschrijving", "").strip()[:80]
        if not re.fullmatch(r"[A-Z0-9*]{1,6}", code):
            flash("Een rolcode bestaat uit 1 tot 6 letters, cijfers of een *.", "danger")
        elif not omschrijving:
            flash("Vul een omschrijving in.", "danger")
        else:
            try:
                db.maak_rol(code, omschrijving)
                flash(f"Rol {code} is toegevoegd.", "success")
            except ValueError as fout:
                flash(str(fout), "danger")
        return redirect(url_for("admin_rollen"))
    return render_template("rollen.html", rollen=db.haal_rollen_beheer(), iconen=icons.ICONEN)


@app.route("/admin/rollen/<int:rol_id>/wijzig", methods=["POST"])
@admin_vereist
def admin_rol_wijzig(rol_id):
    omschrijving = request.form.get("omschrijving", "").strip()[:80]
    if not omschrijving:
        flash("De omschrijving mag niet leeg zijn.", "danger")
    else:
        db.wijzig_rol(rol_id, omschrijving)
        flash("Rol bijgewerkt.", "success")
    return redirect(url_for("admin_rollen"))


@app.route("/admin/rollen/<int:rol_id>/verwijder", methods=["POST"])
@admin_vereist
def admin_rol_verwijder(rol_id):
    try:
        db.verwijder_rol(rol_id)
        flash("Rol verwijderd.", "success")
    except ValueError as fout:
        flash(str(fout), "danger")
    return redirect(url_for("admin_rollen"))

@app.route("/admin/opruimen", methods=["GET", "POST"])
@admin_vereist
def admin_opruimen():
    if request.method == "POST":
        if request.form.get("bevestig") != "ja":
            flash("Vink eerst aan dat je dit zeker weet.", "danger")
            return redirect(url_for("admin_opruimen"))
        pad = db.maak_back_up()
        n = db.wis_handmatige_planning(bool(request.form.get("aantallen")))
        flash(f"{n} handmatige toewijzingen verwijderd. Een back-up staat in {os.path.relpath(pad, app.root_path)}.",
              "success")
        return redirect(url_for("admin_auto"))
    return render_template("opruimen.html", tel=db.tel_planning())

if __name__ == "__main__":
    app.run(debug=True)