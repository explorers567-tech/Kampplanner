# Lijst: vergelijkbaar met een kolom met waarden
namen = ["Lara", "Michel", "Niek", "Yason", "Lars", "Joris", "Jelle", "Menno", "Gerwin"]
namen.append("Yason")
print(len(namen))

# Dictionary: vergelijkbaar met een rij (kolomnaam -> waarde)
persoon = {"naam": "Lara", "ouderraad": False}
print(persoon["naam"])

# Lus met voorwaarde: vergelijkbaar met WHERE
for naam in namen:
    if naam.startswith("L"):
        print(naam)
for naam in namen:
    if naam.startswith("M"):
        print(naam)

# Functie
def groet(naam):
    return f"Hallo {naam}!"

# print(groet("Menno"))