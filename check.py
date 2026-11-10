"""Controleert of alles wat in app.py en de templates wordt gebruikt ook bestaat."""
import ast
import glob
import os
import re

import app
import db
import planner

problemen = []

routes = {r.endpoint for r in app.app.url_map.iter_rules()}
for pad in glob.glob("templates/*.html") + ["app.py"]:
    tekst = open(pad, encoding="utf-8").read()
    for naam in re.findall(r"url_for\(\s*['\"]([\w.]+)['\"]", tekst):
        if naam not in routes:
            problemen.append(f"route '{naam}' bestaat niet (gebruikt in {pad})")

boom = ast.parse(open("app.py", encoding="utf-8").read())
for node in ast.walk(boom):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        module = {"db": db, "planner": planner}.get(node.value.id)
        if module is not None and not hasattr(module, node.attr):
            problemen.append(f"{node.value.id}.{node.attr} bestaat niet (app.py, regel {node.lineno})")

for node in ast.walk(boom):
    if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "render_template"
            and node.args and isinstance(node.args[0], ast.Constant)):
        if not os.path.exists(os.path.join("templates", node.args[0].value)):
            problemen.append(f"template '{node.args[0].value}' ontbreekt (app.py, regel {node.lineno})")

for pad in glob.glob("templates/*.html"):
    for naam in re.findall(r"{%\s*(?:include|extends)\s+['\"]([^'\"]+)['\"]", open(pad, encoding="utf-8").read()):
        if not os.path.exists(os.path.join("templates", naam)):
            problemen.append(f"template '{naam}' ontbreekt (nodig voor {pad})")

if problemen:
    print("Dit klopt niet:")
    for p in problemen:
        print("   -", p)
else:
    print(f"Alles gevonden: {len(routes)} routes, alle db- en planner-functies en alle templates.")