# from openpyxl import load_workbook

# wb = load_workbook("data/WieWatWaarWanneer.xlsx")
# ws = wb.active

# for rij in ws.iter_rows(min_row=2, values_only=True):
#     print(type(rij[1]), rij[1])

# for rij in ws.iter_rows(min_row=2, values_only=True):
#     print(type(rij[2]), rij[2])

# for rij in ws.iter_rows(min_row=2, values_only=True):
#     print(type(rij[3]), rij[3])

# for rij in ws.iter_rows(min_row=2, values_only=True):
#     print(type(rij[4]), rij[4])

from openpyxl import load_workbook

wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active

rijen = list(ws.iter_rows(values_only=True))
kopregel = rijen[0]          # de eerste rij met de namen

telling = {}                 # hier komt per persoon een eigen dictionary in

for rij in rijen[1:]:        # sla de kopregel over
    # TODO: sla de rij over als het geen planningsrij is
    #       (tip: `continue` springt naar de volgende rij in de lus)

    for naam, code in zip(kopregel[4:], rij[4:]):
        # TODO: sla over als naam of code leeg is (None)
        # TODO: haal spaties weg van de code met code.strip()
        # TODO: tel de code op bij deze persoon
        pass

print(telling)