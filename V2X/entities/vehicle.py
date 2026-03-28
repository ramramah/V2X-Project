import logging
import time
import uuid
from typing import Optional
import traci
import config
from .base import Entity
from utils import sumo_to_geo, get_generation_delta_time
from config import VEHICLE_DEFAULTS, STATION_TYPE_RULES

from mqtt_manager import mqtt_manager
from messages import MessageFactory
from stats_logger import stats_logger

logger = logging.getLogger(__name__)

class Vehicle(Entity):
    
    def __init__(self, station_id: int, sumo_id: str, name: Optional[str] = None, station_type: int = 5, length: int = 5, width: int = 2, enabled_messages: Optional[list[str]] = None):
        super().__init__(station_id, name or f"Vehicle_{station_id}")
        self.sumo_id = sumo_id
        self.base_station_type = station_type
        self.length = length
        self.width = width
        self.enabled_messages = enabled_messages or VEHICLE_DEFAULTS.get("enabled_messages", ["cam"])
        self._speed: float = 0.0
        self._heading: float = 0.0
        self._acceleration: float = 0.0
        self._light_left_turn: bool = False
        self._light_right_turn: bool = False
        # AGGIUNTA: Variabili di stato precedente per il rilevamento del cambio
        self._prev_left = False
        self._prev_right = False
        self._last_processed_manoeuvre_id = -1
        self._last_request_trace = {}
        logger.debug(f"Veicolo {self.name} (SUMO: {sumo_id}) creato")
        self.managed_by_python = self.sumo_id in ["1", "2"]
        if not self.managed_by_python:
            logger.info(f"Veicolo {self.sumo_id} creato in modalità SOLO-SUMO (No V2X).")
    
    @classmethod
    def from_sumo(cls, sumo_id: str, station_id: Optional[int] = None) -> "Vehicle":
        from utils import get_station_id_from_veh
        if station_id is None: station_id = get_station_id_from_veh(sumo_id)
        return cls(station_id=station_id, sumo_id=sumo_id, station_type=VEHICLE_DEFAULTS.get("station_type", 5), length=VEHICLE_DEFAULTS.get("length", 5), width=VEHICLE_DEFAULTS.get("width", 2), enabled_messages=VEHICLE_DEFAULTS.get("enabled_messages", ["cam"]))
    
    def update(self, sim_time: float, x: float = None, y: float = None, speed: float = None, heading: float = None, acceleration: float = None, **kwargs) -> None:
        if x is not None and y is not None: self._x = x; self._y = y; self._lat, self._lon = sumo_to_geo(x, y)
        if speed is not None: self._speed = speed
        if heading is not None: self._heading = heading
        if acceleration is not None: self._acceleration = acceleration
        # self._light_left_turn = kwargs.get("light_left_turn", False)
        # self._light_right_turn = kwargs.get("light_right_turn", False)

        # 1. Recupera lo stato attuale delle frecce dai kwargs
        current_left = kwargs.get("light_left_turn", False)
        current_right = kwargs.get("light_right_turn", False)

        if not self.managed_by_python:
            # Aggiorniamo comunque i _prev per evitare glitch se mai dovesse diventare gestito
            self._prev_left = current_left
            self._prev_right = current_right
            return

        # 2. Controllo Freccia SINISTRA
        if current_left and not self._prev_left:
            print(f"[{sim_time:.2f}s] Veicolo {self.sumo_id}: Freccia SINISTRA INSERITA")
        elif not current_left and self._prev_left:
            print(f"[{sim_time:.2f}s] Veicolo {self.sumo_id}: Freccia SINISTRA DISINSERITA")

        # 3. Controllo Freccia DESTRA
        if current_right and not self._prev_right:
            print(f"[{sim_time:.2f}s] Veicolo {self.sumo_id}: Freccia DESTRA INSERITA")
        elif not current_right and self._prev_right:
            print(f"[{sim_time:.2f}s] Veicolo {self.sumo_id}: Freccia DESTRA DISINSERITA")

        # 4. Fondamentale: aggiorna gli stati per il prossimo step
        self._light_left_turn = current_left
        self._light_right_turn = current_right
        self._prev_left = current_left
        self._prev_right = current_right
        

    @property
    def speed(self) -> float: return self._speed
    @property
    def heading(self) -> float: return self._heading
    @property
    def acceleration(self) -> float: return self._acceleration
    
    def should_send_message(self, message_type: str, sim_time: float) -> bool:
        # --- MODIFICA: Se il veicolo non è gestito da Python, NON deve inviare nulla ---
        if not self.managed_by_python:
            return False
            
        return self.is_message_enabled(message_type)
    
    def _resolve_station_type(self, message_type: str) -> int:
        rules = STATION_TYPE_RULES.get("VEHICLE", {})
        if message_type.startswith("mcm"): return rules.get("mcm", 1)
        return self.base_station_type

    def get_message_data(self, message_type: str) -> dict:
        current_station_type = self._resolve_station_type(message_type)
        return { "station_id": self.station_id, "station_type": current_station_type, "lat": self._lat, "lon": self._lon, "speed": self._speed, "heading": self._heading, "acceleration": self._acceleration, "length": self.length, "width": self.width, "light_left_turn": self._light_left_turn, "light_right_turn": self._light_right_turn }
    
    def get_state_snapshot(self) -> dict: return { "x": self._x, "y": self._y, "speed": self._speed, "heading": self._heading }
    
    def handle_mcm_request(self, payload: dict):
        """
        Elabora una MCM Request ricevuta dal RSU.
        FLUSSO: 
        1. Analizza richiesta
        2. Invia MCM Response (Accept)
        3. Esegue azione (Stop o Priority)
        """
        if not self.managed_by_python:
            return
        self._last_request_trace = payload.get("trace", {}) or {}
        mcm_container = payload.get("mcmContainer", {})
        basic_container = payload.get("basicContainer", {})
        advised_container = mcm_container.get("advisedManoeuvreContainer", [])

        # Recuperiamo il Manoeuvre ID dalla request per usarlo nella response
        manoeuvre_id = basic_container.get("manoeuvreId", 0)

        # Se ho già risposto a questa manovra, ignoro il messaggio
        if self._last_processed_manoeuvre_id == manoeuvre_id:
            return

        # Cerca istruzioni per ME
        my_instruction = next((entry for entry in advised_container if entry.get("executantID") == self.station_id), None)
        
        if not my_instruction:
            return 

        # Aggiorno memoria: ho preso in carico questa richiesta
        self._last_processed_manoeuvre_id = manoeuvre_id
        
        advised_change = my_instruction.get("currentStateAdvisedChange", {})
        
        logger.info(f"Veicolo {self.name}: Nuova Request (Manoeuvre ID: {manoeuvre_id}). Invio Response.")

        # --- FASE 1: INVIA MCM RESPONSE ---
        # Prima di agire fisicamente, inviamo la conferma
        self._send_mcm_response(manoeuvre_id, accepted=True)

        # --- FASE 2: ESECUZIONE FISICA (TRIGGER) ---
        advised_change = my_instruction.get("currentStateAdvisedChange", {})
        
        if "stop" in advised_change:
            self._perform_slow_down()
            
        elif "driveStraight" in advised_change or "stayInLane" in advised_change:
            self._perform_priority_passage()
            
        else:
            logger.debug(f"Veicolo {self.name}: Strategia ignota. Nessuna azione fisica.")

    def _perform_emergency_stop(self):
        """Esegue stop sicuro."""
        try:
            current_lane_id = traci.vehicle.getLaneID(self.sumo_id)
            current_edge_id = traci.lane.getEdgeID(current_lane_id)
            
            # PROTEZIONE: Se siamo su un edge interno (incrocio), NON fermarti.
            if current_edge_id.startswith(":"):
                logger.warning(f"Veicolo {self.name}: Ignorato STOP su edge interno (Incrocio).")
                return 

            logger.warning(f"Veicolo {self.name}: STRATEGIA 'STOP' RICEVUTA. Eseguo manovra di arresto.")
            traci.vehicle.setColor(self.sumo_id, (255, 0, 255)) 
            traci.vehicle.setSpeedMode(self.sumo_id, 0)
            
            current_pos = traci.vehicle.getLanePosition(self.sumo_id)
            lane_len = traci.lane.getLength(current_lane_id)
            target_pos = lane_len - 1.0 

            # Anti-overshoot
            if target_pos <= current_pos + 5.0:
                target_pos = min(current_pos + 10.0, lane_len - 0.5)

            traci.vehicle.setStop(vehID=self.sumo_id, edgeID=current_edge_id, pos=target_pos, laneIndex=0, duration=1.0)
        except traci.TraCIException as e:
            logger.error(f"Errore critico stop {self.name}: {e}")

    def _perform_priority_passage(self):
        """Esegue passaggio prioritario."""
        logger.info(f"Veicolo {self.name}: STRATEGIA 'PRIORITY' RICEVUTA. Procedo.")
        try:
            traci.vehicle.setColor(self.sumo_id, (0, 0, 255))
            traci.vehicle.setSpeedMode(self.sumo_id, 55)
            traci.vehicle.setSpeed(self.sumo_id, 14.0) 
        except traci.TraCIException as e:
            logger.error(f"Errore priorità {self.name}: {e}")

    def _perform_slow_down(self):
        """
        Rallenta il veicolo a una velocità di sicurezza invece di fermarlo.
        Simula un comportamento di 'Yield' o approccio lento all'incrocio.
        """
        target_speed = 4.0  # 5 m/s (circa 18 km/h) - Modifica a piacere
        
        logger.info(f"Veicolo {self.name}: RALLENTO a {target_speed} m/s per dare precedenza.")
        
        try:
            # Cambio colore in ARANCIONE per feedback visivo nella GUI
            traci.vehicle.setColor(self.sumo_id, (255, 165, 0)) 
            
            # Opzione A: Cambio istantaneo del limite di velocità
            # traci.vehicle.setSpeed(self.sumo_id, target_speed)
            
            # Opzione B (Più realistica): Decelerazione fluida in 3 secondi
            traci.vehicle.slowDown(self.sumo_id, target_speed, 1.0)
            
        except traci.TraCIException as e:
            logger.error(f"Errore rallentamento {self.name}: {e}")

    def handle_mcm_termination(self, payload: dict):
        """
        Gestisce il messaggio di fine manovra.
        Ripristina la velocità e il colore originale del veicolo.
        """
        if not self.managed_by_python:
            return

        logger.info(f"Veicolo {self.name}: Ricevuto MCM TERMINATION. Ripristino guida normale.")

        try:
            # 1. Ripristina il controllo automatico della velocità
            # Questo annulla sia setSpeed che slowDown
            traci.vehicle.setSpeed(self.sumo_id, -1.0)
            
            # 2. Controllo preventivo degli Stop
            # Recuperiamo la lista dei futuri stop. Se è vuota, NON chiamiamo resume.
            # Questo evita l'errore "Failed to resume... it has no stops" nel log.
            future_stops = traci.vehicle.getNextStops(self.sumo_id)
            if future_stops:
                traci.vehicle.resume(self.sumo_id)
                logger.debug(f"Veicolo {self.name}: Stop rimosso con successo.")

            # 3. Ripristina il colore originale
            if self.sumo_id == "2":
                traci.vehicle.setColor(self.sumo_id, (0, 255, 0)) # Verde
            else:
                traci.vehicle.setColor(self.sumo_id, (255, 0, 0)) # Rosso
                
        except traci.TraCIException as e:
            logger.error(f"Errore ripristino veicolo {self.name}: {e}")

    def _send_mcm_response(self, manoeuvre_id: int, accepted: bool):
        """
        Costruisce e invia il messaggio MCM Response tramite MQTT.
        """
        try:
            sim_time = traci.simulation.getTime()
            gen_delta_time = get_generation_delta_time(sim_time)

            message = MessageFactory.create("mcm_response", gen_delta_time)
            if not message:
                logger.error("Impossibile creare MCM Response: Factory ha fallito.")
                return

            response_data = self.get_message_data("mcm_response")
            response_data.update({
                "manoeuvre_id": manoeuvre_id,
                "response_code": 0 if accepted else 1,
                "cost": 0,
            })

            payload = message.build_payload(response_data)

            trace = {
                "message_id": str(uuid.uuid4()),
                "session_id": self._last_request_trace.get("session_id", f"session_fallback_{manoeuvre_id}"),
                "python_tx_wall_time": time.time(),
                "python_tx_sim_time": sim_time,
                "msg_type": "mcm_response",
                "sender_station_id": self.station_id,
            }
            payload["trace"] = trace

            topic = "vanetza/in/mcm"

            if config.APP_TX_DROP_PROB > 0.0:
                import random
                if random.random() < config.APP_TX_DROP_PROB:
                    if config.ENABLE_STATS_LOGGING:
                        stats_logger.log_message_event(
                            wall_time=time.time(),
                            sim_time=sim_time,
                            direction="drop",
                            topic=topic,
                            msg_type="mcm_response",
                            station_id=self.station_id,
                            receiver_id="",
                            manoeuvre_id=manoeuvre_id,
                            session_id=trace["session_id"],
                            message_id=trace["message_id"],
                            python_tx_wall_time=trace["python_tx_wall_time"],
                            python_tx_sim_time=trace["python_tx_sim_time"],
                            delay_ms="",
                            raw_json=payload,
                        )
                    return

            if config.APP_TX_DELAY_MS > 0:
                time.sleep(config.APP_TX_DELAY_MS / 1000.0)

            mqtt_manager.publish(self.station_id, "mcm_response", payload)

            if config.ENABLE_STATS_LOGGING:
                stats_logger.log_message_event(
                    wall_time=trace["python_tx_wall_time"],
                    sim_time=sim_time,
                    direction="tx",
                    topic=topic,
                    msg_type="mcm_response",
                    station_id=self.station_id,
                    receiver_id="",
                    manoeuvre_id=manoeuvre_id,
                    session_id=trace["session_id"],
                    message_id=trace["message_id"],
                    python_tx_wall_time=trace["python_tx_wall_time"],
                    python_tx_sim_time=trace["python_tx_sim_time"],
                    delay_ms="",
                    raw_json=payload,
                )

            logger.info(f"Veicolo {self.name}: MCM Response inviata (Accettata={accepted})")

        except Exception as e:
            logger.error(f"Errore durante l'invio della MCM Response per {self.name}: {e}")
    def _prepare_mcm_response(self, accepted: bool): pass
