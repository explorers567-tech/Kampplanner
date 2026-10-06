from openpyxl import load_workbook

wb = load_workbook("data/WieWatWaarWanneer.xlsx")
ws = wb.active

namen = []

# Print de eerste 5 rijen om te zien wat erin staat
for rij in ws.iter_rows(max_row=1, values_only=True):
    for cel in rij[4:]:
        if cel is not None:
            namen.append(cel)
    
print(namen)
print(f"aantal personen: {len(namen)}")