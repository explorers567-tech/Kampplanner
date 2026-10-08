from datetime import time   # bovenaan je bestand, bij de andere imports
from openpyxl import load_workbook

wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active

rijen = list(ws.iter_rows(values_only=True))
kopregel = rijen[0]          # de eerste rij met de namen

telling = {}                 # hier komt per persoon een eigen dictionary in

for rij in rijen[1:]:
    if not isinstance(rij[1], time):
        continue
    # print(rij[1])   # tijdelijk, om te controleren

    for naam, code in zip(kopregel[4:], rij[4:]):
        if naam is None or code is None:
            continue
        code = str(code).strip()
        if code == "":
            continue
        # print(naam, code)   # tijdelijk
        pass
        if naam not in telling:
            telling[naam] = {}
        telling[naam][code] = telling[naam].get(code, 0) + 1
        # print(f"{naam} heeft code {code} {telling[naam][code]} keer gezien.")
        for naam, codes in telling.items():
         print(f"{naam}: {codes}")