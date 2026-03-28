import os
import sys
import subprocess
import time
from itertools import product

# ==========================================
# CONFIGURAZIONE AUTOMATICA
# ==========================================
# 1. Numero veicoli: da 2 a 52, step 10 -> [2, 12, 22, 32, 42, 52]
VEHICLE_COUNTS = range(2, 53, 10)

# 2. Seeds: da 0 a 50, step 10 -> [0, 10, 20, 30, 40, 50]
SEEDS = range(0, 51, 10)

# 3. Modalità
MODES = ["BASELINE", "V2X"]

OUTPUT_DIR = "batch_results"
ROUTES_DIR = "temp_routes"
# ==========================================

def generate_route_file(filename, n_vehicles):
    """
    Genera file .rou.xml:
    - Veicoli 1 e 2 sempre presenti (Scenario V2X fisso)
    - Veicoli 3...N aggiunti come traffico di sfondo
    """
    content = """<routes>
    <route id="route0" edges="A3B3 B3B4"/>
    <route id="route1" edges="C3B3 B3A3"/>
    <vType id="type1" accel="0.8" decel="7.5" sigma="0.5" length="5" maxSpeed="27.7"/>
    
    <vehicle id="1" type="type1" depart="0" route="route0" color="1,0,0"/>
    <vehicle id="2" type="type1" depart="0" route="route1" color="0,1,0"/>
    """
    
    # Traffico di sfondo (Veicoli 3 -> N)
    for i in range(3, n_vehicles + 1):
        # Alterna le rotte per creare congestione su entrambi i lati
        route = "route0" if i % 2 != 0 else "route1"
        # Partenze scalate ogni 2-3 secondi per evitare collisioni alla nascita
        depart = (i - 2) * 3 
        content += f'    <vehicle id="{i}" type="type1" depart="{depart}" route="{route}" color="1,1,0"/>\n'
    
    content += "</routes>"
    
    with open(filename, "w") as f:
        f.write(content)

def run_batch():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists(ROUTES_DIR): os.makedirs(ROUTES_DIR)

    combinations = list(product(VEHICLE_COUNTS, SEEDS, MODES))
    total = len(combinations)
    
    print(f"=== INIZIO BATCH: {total} Simulazioni ===")
    
    start_time_all = time.time()

    for idx, (n_veh, seed, mode) in enumerate(combinations, 1):
        print(f"[{idx}/{total}] Mode={mode}, Veh={n_veh}, Seed={seed}...", end=" ", flush=True)
        
        # 1. Genera Rotta
        route_file = os.path.join(ROUTES_DIR, f"cars_{n_veh}.rou.xml")
        generate_route_file(route_file, n_veh)
        
        # 2. Definisci Output univoco
        prefix = f"{OUTPUT_DIR}/{mode}_v{n_veh}_s{seed}"
        
        # 3. Comando
        cmd = [
            sys.executable, "main.py",
            "--mode", mode,
            "--seed", str(seed),
            "--route-file", route_file,
            "--prefix", prefix,
            "--nogui"
        ]
        
        try:
            t0 = time.time()
            # capture_output=True nasconde i log di SUMO per pulizia
            subprocess.run(cmd, check=True, capture_output=True) 
            dt = time.time() - t0
            print(f"OK ({dt:.2f}s)")
        except subprocess.CalledProcessError as e:
            print(f"ERRORE!")
            # Stampa l'errore se serve debugging
            # print(e.stderr.decode())

    tot_time = time.time() - start_time_all
    print(f"\n=== COMPLETATO in {tot_time:.1f}s. Risultati in '{OUTPUT_DIR}' ===")

if __name__ == "__main__":
    run_batch()