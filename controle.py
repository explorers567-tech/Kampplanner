import glob
import re

import app

routes = {r.endpoint for r in app.app.url_map.iter_rules()}
bestanden = glob.glob("templates/*.html") + ["app.py"]
ontbreekt = set()
for pad in bestanden:
    tekst = open(pad, encoding="utf-8").read()
    for naam in re.findall(r"url_for\(\s*['\"]([\w.]+)['\"]", tekst):
        if naam not in routes:
            ontbreekt.add((pad, naam))

if ontbreekt:
    print("Deze routes worden gebruikt maar bestaan niet:")
    for pad, naam in sorted(ontbreekt):
        print(f"   {naam}   (gebruikt in {pad})")
else:
    print(f"Alle routes die in de templates en in app.py worden gebruikt bestaan ({len(routes)} routes).")