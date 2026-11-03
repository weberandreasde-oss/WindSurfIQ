
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

ALT = BASE / "surfspots.json"
NEU = BASE / "surfspots_1113_markers.json"
ZIEL = BASE / "surfspots_merged_1155.json"


def lade_spots(datei):
    with datei.open("r", encoding="utf-8") as f:
        daten = json.load(f)

    # Alter Katalog: Objekt mit "spots"
    # Neuer Katalog: direkte Liste
    if isinstance(daten, dict):
        daten = daten["spots"]

    if not isinstance(daten, list):
        raise ValueError(f"Ungueltiges Format: {datei.name}")

    return daten


alte_spots = lade_spots(ALT)
neue_spots = lade_spots(NEU)

alle_spots = []
ids = set()

for quelle, spots in [
    ("original", alte_spots),
    ("geocoded", neue_spots),
]:
    for nummer, spot in enumerate(spots, 1):
        eintrag = spot.copy()

        # Unterschiedliche Einstiege bleiben erhalten.
        # Keine Zusammenlegung nach Namen oder Entfernung.
        original_id = str(eintrag.get("id") or nummer)
        neue_id = original_id

        if neue_id in ids:
            neue_id = f"{quelle}-{original_id}"

        if neue_id in ids:
            raise ValueError(f"Doppelte ID: {neue_id}")

        eintrag["id"] = neue_id
        ids.add(neue_id)

        # Einheitliches Koordinatenformat
        eintrag["lat"] = float(eintrag["lat"])
        eintrag["lon"] = float(eintrag["lon"])
        eintrag["lng"] = eintrag["lon"]

        if quelle == "geocoded":
            eintrag["verified"] = False
            eintrag["coordinateAccuracy"] = (
                "approximate; not verified launch point"
            )
            eintrag.setdefault(
                "region",
                eintrag.get("place") or eintrag.get("country", "")
            )

        alle_spots.append(eintrag)

erwartet = len(alte_spots) + len(neue_spots)

assert len(alle_spots) == erwartet
assert len(ids) == erwartet

with ZIEL.open("w", encoding="utf-8") as f:
    json.dump(
        alle_spots,
        f,
        ensure_ascii=False,
        indent=2
    )

print(f"Alte Spots: {len(alte_spots)}")
print(f"Neue Spots: {len(neue_spots)}")
print(f"Gesamt: {len(alle_spots)}")
print(f"Gespeichert: {ZIEL.name}")

