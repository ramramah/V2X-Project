import os
import xml.etree.ElementTree as ET
from config import OUTPUT_DIR

def get_stats(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # vehicleTripStatistics contiene i dati aggregati
        stats = root.find("vehicleTripStatistics")
        return {
            "duration": float(stats.get("duration")),
            "waitingTime": float(stats.get("waitingTime")),
            "timeLoss": float(stats.get("timeLoss")),
            "speed": float(stats.get("speed"))
        }
    except Exception as e:
        print(f"Errore lettura {filename}: {e}")
        return None

base = get_stats("baseline_stats.xml")
v2x = get_stats("v2x_stats.xml")

print(f"\nCONFRONTO RISULTATI (Cartella: {OUTPUT_DIR})")
print("=" * 65)
print(f"{'METRICA':<20} | {'BASELINE':<10} | {'V2X':<10} | {'DELTA':<10}")
print("-" * 65)

if base and v2x:
    metrics = [
        ("Waiting Time (s)", "waitingTime"), # Tempo fermi
        ("Time Loss (s)", "timeLoss"),       # Tempo perso rallentando
        ("Duration (s)", "duration"),        # Durata totale viaggio
        ("Avg Speed (m/s)", "speed")         # Velocità media
    ]
    
    for label, key in metrics:
        val_b = base[key]
        val_v = v2x[key]
        delta = val_v - val_b
        print(f"{label:<20} | {val_b:<10.2f} | {val_v:<10.2f} | {delta:<+10.2f}")
else:
    print("File mancanti. Assicurati di aver eseguito entrambe le modalità.")
    print(f"Cercati in: {OUTPUT_DIR}/baseline_stats.xml e v2x_stats.xml")