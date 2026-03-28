import os
import xml.etree.ElementTree as ET
import csv

OUTPUT_DIR = "batch_results"
CSV_FILE = "final_results.csv"

def analyze():
    print(f"Analisi file in {OUTPUT_DIR}...")
    
    results = []
    
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith("_stats.xml"):
            continue
            
        # Nome file atteso: BASELINE_v22_s10_stats.xml
        try:
            parts = filename.replace("_stats.xml", "").split("_")
            mode = parts[0]
            n_veh = int(parts[1].replace("v", ""))
            seed = int(parts[2].replace("s", ""))
            
            tree = ET.parse(os.path.join(OUTPUT_DIR, filename))
            stats = tree.getroot().find("vehicleTripStatistics")
            
            if stats is not None:
                results.append({
                    "Mode": mode,
                    "Vehicles": n_veh,
                    "Seed": seed,
                    "Waiting Time": float(stats.get("waitingTime")),
                    "Time Loss": float(stats.get("timeLoss")),
                    "Duration": float(stats.get("duration")),
                    "Speed": float(stats.get("speed"))
                })
        except Exception as e:
            print(f"Skipping {filename}: {e}")

    # Ordina per facilità di lettura
    results.sort(key=lambda x: (x["Vehicles"], x["Seed"], x["Mode"]))
    
    # Scrittura CSV
    if results:
        keys = results[0].keys()
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        print(f"Salvato: {CSV_FILE} ({len(results)} righe)")
    else:
        print("Nessun risultato trovato.")

if __name__ == "__main__":
    analyze()