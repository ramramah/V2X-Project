"""
Funzioni di utilità per il simulatore V2X.
"""

import math
import time
import traci


def sumo_to_geo(x_sumo: float, y_sumo: float) -> tuple[float, float]:
    """
    Converte coordinate cartesiane SUMO in Lat/Lon.
    
    Args:
        x_sumo: Coordinata X in SUMO
        y_sumo: Coordinata Y in SUMO
        
    Returns:
        Tupla (latitude, longitude)
    """
    lon, lat = traci.simulation.convertGeo(x_sumo, y_sumo)
    return lat, lon


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calcola la distanza euclidea tra due punti."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def get_station_id_from_veh(veh_id: str) -> int:
    """
    Estrae un numero intero dall'ID veicolo SUMO.
    
    Es: 'obu_1' -> 1, 'vehicle_42' -> 42
    """
    try:
        return int(''.join(filter(str.isdigit, veh_id)))
    except ValueError:
        return abs(hash(veh_id)) % 100000


def get_generation_delta_time(sim_time_sec: float) -> int:
    """
    Calcola il generationDeltaTime (TimestampIts mod 65536).
    Conforme a ETSI TS 102 894-2.
    
    Args:
        sim_time_sec: Tempo di simulazione in secondi
        
    Returns:
        Valore TimestampIts (0-65535)
    """
    base_time_ms = int(time.time() * 1000)
    current_ms = base_time_ms + int(sim_time_sec * 1000)
    return current_ms % 65536


def heading_difference(h1: float, h2: float) -> float:
    """Calcola la differenza minima tra due heading (0-180)."""
    diff = abs(h1 - h2)
    if diff > 180:
        diff = 360 - diff
    return diff
