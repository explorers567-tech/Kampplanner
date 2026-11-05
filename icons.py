"""Pictogrammen voor rolcodes, in scoutingstijl.

Pas dit bestand gerust aan: links de rolcode (zoals in de tabel roles), rechts het
pictogram. Een code die hier niet in staat, wordt gewoon als tekst getoond.
Zie je een vierkantje in plaats van een plaatje? Dan kent jouw apparaat dat
emoji nog niet. Kies dan een ander pictogram.
"""
ICONEN = {
    # aanwezigheid
    "#":  "🏠",      # afwezig
    "?":  "❓",      # onbekend
    # spel
    "L":  "L",      # aanwezig bij spel als leiding (kampvuur)
    "V":  "🗺️",      # voorbereiding spel (kaart)
    "VL": "🗺️L",    # voorbereiding + aanwezig
    "O":  "🚩",      # organisatie spel (vlag)
    "OA": "🚩🙋",    # organisatie + aanspreekpunt
    # slapen en opstaan
    "K":  "🌙",      # kids naar bed brengen & oppassen
    "K*": "🛏️🌙",    # bedden klaarleggen + naar bed brengen
    "OK": "🌳",      # oppassen op kids buiten
    "W":  "📯",      # alle blokhutten wekken (hoorn)
    # eten en drinken
    "BS": "🥪",      # brood smeren
    "OB": "🔨",      # opbouwen
    "A":  "🧽",      # afwas
    "BD": "🍽️",      # bedienen diner
    "BB": "🍹",      # bedienen borrel
    "XX": "🍳",      # catering voorbereiden
    "M":  "🥤",      # limo / chocomel maken
    # schoonmaken en opruimen
    "TW": "🚽🐺",    # toiletten welpenblokhut (wolf)
    "TB": "🚽🦫",    # toiletten beverblokhut (bever)
    "TS": "🚽⛺",    # toilet stamkant (tent)
    "TV": "🚽🥾",    # toilet verkennerkant (wandelschoen)
    "S":  "🧹",      # stamblokhut opruimen
    # disco
    "OD": "🕺",      # omkleden disco + aanwezig
    "OO": "🕺🧹",    # omkleden disco + opruimen
}