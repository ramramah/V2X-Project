import uuid#!/usr/bin/env python3
"""
V2X Simulator - Entry Point (Batch Mode Enabled)
"""

import sys
import time
import logging
import json
import argparse  # <--- AGGIUNTO
from typing import Optional
import uuid
import traci
import sumolib
import random


# Configurazione
import config # Importiamo il modulo intero per modificarlo runtime
from config import (
    SUMO_CFG, SUMO_STEP_LENGTH, SUMO_GUI,
    RSU_CONFIG, LOGGING, STATIONS, MQTT_TOPICS
)

# Moduli interni
from utils import get_station_id_from_veh, get_generation_delta_time, euclidean_distance
from mqtt_manager import mqtt_manager
from entities import RSU, Vehicle
from messages import MessageFactory
from triggers import TriggerRegistry
from triggers.mcm_trigger import RSUMCMRequestTrigger
from stats_logger import stats_logger

logging.basicConfig(
    level=getattr(logging, LOGGING.get("level", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("V2X_Simulator")


class V2XSimulator:
    
    def __init__(self, route_override=None, output_prefix="run"):
        self.route_override = route_override
        self.output_prefix = output_prefix

        self.rsus: dict[int, RSU] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self.vehicle_trigger_states: dict[str, dict[str, dict]] = {}
        self.triggers = {}
        self._running = False
        self._incoming_mcm_queue = []

        self._current_session_id = None

    def initialize(self):
        if config.ENABLE_STATS_LOGGING:
            stats_logger.initialize(
                prefix=self.output_prefix,
                output_dir=config.STATS_OUTPUT_DIR
            )

        # 1. Avvia SUMO
        self._start_sumo()

        if config.SIMULATION_MODE == "BASELINE":
            logger.info("Modalità BASELINE attiva: Logica V2X disabilitata.")
            return

        # 2. Crea RSU e Trigger (Solo V2X)
        self._initialize_rsus()
        self._initialize_triggers()
        self._setup_mqtt_listeners()

        logger.info("Simulatore inizializzato (V2X Attivo)")
    def _setup_mqtt_listeners(self):
        for client_id in range(3):
            listener_client = mqtt_manager.get_client(client_id)

            if listener_client:
                listener_client.on_message = self._on_mqtt_message

                topics = [
                    MQTT_TOPICS["mcm"],
                    MQTT_TOPICS["cam"],
                ]

                for topic in topics:
                    listener_client.subscribe(topic)

                logger.info(f"Ascolto attivo su topic MQTT: {topic}")


    def _safe_sim_time(self):
        try:
            return traci.simulation.getTime()
        except Exception:
            return None

    def _infer_msg_type(self, topic, payload):
        if topic == MQTT_TOPICS["cam"]:
            return "cam"

        basic = payload.get("basicContainer", {})
        mcm_type = basic.get("mcmType")

        mapping = {
            1: "mcm_request",
            2: "mcm_response",
            4: "mcm_termination",
        }
        return mapping.get(mcm_type, "mcm")

    def _make_trace_for_payload(self, msg_type, entity, sim_time, data):
        manoeuvre_id = data.get("manoeuvre_id", "")
        now = time.time()

        if msg_type == "mcm_request":
            session_id = f"session_{entity.station_id}_{manoeuvre_id}_{int(now * 1000)}"
            self._current_session_id = session_id
        elif msg_type == "mcm_termination" and self._current_session_id:
            session_id = self._current_session_id
        else:
            session_id = data.get("session_id", "")

        return {
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "python_tx_wall_time": now,
            "python_tx_sim_time": sim_time,
            "msg_type": msg_type,
            "sender_station_id": entity.station_id,
        }

    def _extract_receiver_id(self, msg_type, payload):
        if msg_type == "mcm_request":
            advised = payload.get("mcmContainer", {}).get("advisedManoeuvreContainer", [])
            ids = [item.get("executantID") for item in advised if item.get("executantID") is not None]
            return ",".join(map(str, ids))
        return ""

    def _log_rx_event(self, topic, payload):
        msg_type = self._infer_msg_type(topic, payload)
        trace = payload.get("trace", {})
        basic = payload.get("basicContainer", {})
        wall_time = time.time()
        sim_time = self._safe_sim_time()

        python_tx_wall_time = trace.get("python_tx_wall_time")
        delay_ms = "" 
        if python_tx_wall_time is not None:
            delay_ms = (wall_time - python_tx_wall_time) * 1000.0

        stats_logger.log_message_event(
            wall_time=wall_time,
            sim_time=sim_time,
            direction="rx",
            topic=topic,
            msg_type=msg_type,
            station_id=basic.get("stationID", ""),
            receiver_id="",
            manoeuvre_id=basic.get("manoeuvreId", ""),
            session_id=trace.get("session_id", ""),
            message_id=trace.get("message_id", ""),
            python_tx_wall_time=trace.get("python_tx_wall_time", ""),
            python_tx_sim_time=trace.get("python_tx_sim_time", ""),
            delay_ms=delay_ms,
            raw_json=payload,
        )
    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            msg_type = self._infer_msg_type(msg.topic, payload)
  
            if config.ENABLE_STATS_LOGGING:
                self._log_rx_event(msg.topic, payload)

            if msg_type.startswith("mcm"):
                self._incoming_mcm_queue.append(payload)

        except Exception as e:
            logger.error(f"Errore parsing MQTT: {e}")    
    def _start_sumo(self):
        """Avvia la simulazione SUMO con parametri dinamici."""
        binary = "sumo-gui" if config.SUMO_GUI else "sumo"
        sumo_binary = sumolib.checkBinary(binary)
        
        cmd = [
            sumo_binary,
            "-c", SUMO_CFG,
            "--step-length", str(SUMO_STEP_LENGTH),
            "--seed", str(config.SUMO_SEED) # Usa il seed aggiornato
        ]

        # --- MODIFICA QUI: Gestione Automatica GUI ---
        if config.SUMO_GUI:
            cmd.extend([
                "--start",       # Premi "Play" automaticamente
                "--quit-on-end"  # Chiudi la finestra alla fine
            ])
        
        # --- OVERRIDE FILE ROTTE ---
        if self.route_override:
            cmd.extend(["--route-files", self.route_override])
            logger.info(f"Override Rotte: {self.route_override}")
        
        # Aggiunge argomenti statistiche (aggiornati nel main)
        cmd.extend(config.get_sumo_output_args())
        
        traci.start(cmd)
        logger.info(f"SUMO avviato - Mode: {config.SIMULATION_MODE} - Seed: {config.SUMO_SEED}")
    
    def _initialize_rsus(self):
        for rsu_id, cfg in RSU_CONFIG.items():
            try:
                rsu = RSU(rsu_id, cfg["position"], broadcast_interval=cfg.get("broadcast_interval", 1.0), enabled_messages=cfg.get("enabled_messages", ["cam"]))
                self.rsus[rsu_id] = rsu
            except Exception as e:
                logger.error(f"Errore RSU {rsu_id}: {e}")
    
    def _initialize_triggers(self):
        for msg_type in MessageFactory.get_available_types():
            trigger = TriggerRegistry.get(msg_type)
            if trigger: self.triggers[msg_type] = trigger
    
    def run(self):
        self._running = True
        try:
            while self._running and traci.simulation.getMinExpectedNumber() > 0:
                self._process_incoming_messages()
                traci.simulationStep()
                
                sim_time = traci.simulation.getTime()
                gen_delta_time = get_generation_delta_time(sim_time)
                
                self._process_rsus(sim_time, gen_delta_time)
                self._process_vehicles(sim_time, gen_delta_time)
                self._cleanup_vehicles()

                # --- MODIFICA QUI: GESTIONE VELOCITÀ ---
                if config.SUMO_GUI:
                    # Se c'è la grafica, rallenta per simulare il tempo reale (0.1s = 100ms)
                    # Questo permette anche a Vanetza di "stare al passo"
                    time.sleep(0.01) 
                else:
                    # Se siamo in batch (senza grafica), vai alla massima velocità possibile
                    time.sleep(0.01)    # se minore, il container di vanetza_nap, esclude un elemento dello scenario, obu's, rsu's(randomicamente)

        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _process_incoming_messages(self):
        while self._incoming_mcm_queue:
            payload = self._incoming_mcm_queue.pop(0)
            basic = payload.get("basicContainer", {})
            mcm_type = basic.get("mcmType")

            if mcm_type == 1:
                self._dispatch_mcm_request(payload)
            elif mcm_type == 2:
                self._dispatch_mcm_response(payload)
            elif mcm_type == 4:
                self._dispatch_mcm_termination(payload)
    def _dispatch_mcm_termination(self, payload):
        trace = payload.get("trace", {})
        session_id = trace.get("session_id", "")
        sim_time = self._safe_sim_time()
        wall_time = time.time()

        if config.ENABLE_STATS_LOGGING and session_id:
            stats_logger.mark_termination_rx(session_id, wall_time, sim_time)

        for vehicle_obj in self.vehicles.values():
            if vehicle_obj.managed_by_python:
                vehicle_obj.handle_mcm_termination(payload)
    def _dispatch_mcm_request(self, payload):
        container = payload.get("mcmContainer", {}).get("advisedManoeuvreContainer", [])
        target_ids = [item["executantID"] for item in container if "executantID" in item]
        if not target_ids:
            return

        for vehicle_obj in self.vehicles.values():
            if vehicle_obj.station_id in target_ids:
                vehicle_obj.handle_mcm_request(payload)
    def _dispatch_mcm_response(self, payload):
        trace = payload.get("trace", {})
        session_id = trace.get("session_id", "")
        sim_time = self._safe_sim_time()
        wall_time = time.time()

        if config.ENABLE_STATS_LOGGING and session_id:
            stats_logger.mark_response_rx(session_id, wall_time, sim_time)

        logger.info(f"Ricevuta MCM RESPONSE per sessione {session_id}")
    def _process_rsus(self, sim_time: float, gen_delta_time: int):
        # Snapshot semplificato per performance
        world_vehicles = []
        for v in self.vehicles.values():
            snap = v.get_state_snapshot()
            snap.update({"id": v.sumo_id, "station_id": v.station_id, "light_left_turn": v._light_left_turn, "light_right_turn": v._light_right_turn})
            world_vehicles.append(snap)

        for rsu in self.rsus.values():
            for msg_type in rsu.enabled_messages:
                should_send = False
                if msg_type == "cam":
                    should_send = rsu.should_send_message(msg_type, sim_time)
                elif msg_type in self.triggers:
                    should_send = self._evaluate_rsu_trigger(rsu, msg_type, sim_time, world_vehicles)

                if should_send:
                    self._send_message(rsu, msg_type, gen_delta_time)
                    rsu.mark_message_sent(msg_type, sim_time)
    
    def _evaluate_rsu_trigger(self, rsu, msg_type, sim_time, world_vehicles):
        trigger = self.triggers.get(msg_type)
        if not trigger: return False

        rsu_neighbors = []
        for v in world_vehicles:
            dist = euclidean_distance(rsu._x, rsu._y, v["x"], v["y"])
            if dist <= 100: # Ottimizzazione: passa solo veicoli vicini
                v_copy = v.copy()
                v_copy["distance_to_rsu"] = dist
                rsu_neighbors.append(v_copy)

        current_state = rsu.get_state_snapshot()
        current_state["neighbors"] = rsu_neighbors
        
        key = f"rsu_{rsu.station_id}"
        if key not in self.vehicle_trigger_states: self.vehicle_trigger_states[key] = {}
        prev_state = self.vehicle_trigger_states[key].get(msg_type)

        result = trigger.evaluate(str(rsu.station_id), sim_time, current_state, prev_state)

        if result.new_state: self.vehicle_trigger_states[key][msg_type] = result.new_state
        if result.should_send:
            if result.new_state and "current_targets" in result.new_state:
                rsu.set_mcm_targets(result.new_state["current_targets"])
            return True
        return False
    
    def _process_vehicles(self, sim_time, gen_delta_time):
        for veh_id in traci.vehicle.getIDList():
            if veh_id not in self.vehicles: self._register_vehicle(veh_id)
            v = self.vehicles[veh_id]
            x, y = traci.vehicle.getPosition(veh_id)
            v.update(sim_time, x=x, y=y, speed=traci.vehicle.getSpeed(veh_id), heading=traci.vehicle.getAngle(veh_id), acceleration=traci.vehicle.getAcceleration(veh_id), light_left_turn=(traci.vehicle.getSignals(veh_id) & 2) != 0, light_right_turn=(traci.vehicle.getSignals(veh_id) & 1) != 0)
            
            for msg in v.enabled_messages:
                self._evaluate_and_send(v, msg, sim_time, gen_delta_time)
    
    def _register_vehicle(self, sumo_id):
        v = Vehicle.from_sumo(sumo_id)
        self.vehicles[sumo_id] = v
        self.vehicle_trigger_states[sumo_id] = {}
    
    def _evaluate_and_send(self, vehicle, msg_type, sim_time, gen_delta_time):
        trigger = self.triggers.get(msg_type)
        if not trigger: return
        
        prev = self.vehicle_trigger_states.get(vehicle.sumo_id, {}).get(msg_type)
        res = trigger.evaluate(vehicle.sumo_id, sim_time, vehicle.get_state_snapshot(), prev)
        
        if res.should_send:
            self._send_message(vehicle, msg_type, gen_delta_time)
            if res.new_state: self.vehicle_trigger_states[vehicle.sumo_id][msg_type] = res.new_state
    
    def _send_message(self, entity, msg_type, gen_delta_time):
        msg = MessageFactory.create(msg_type, gen_delta_time)
        if not msg:
            return

        sim_time = self._safe_sim_time()
        data = entity.get_message_data(msg_type)
        payload = msg.build_payload(data)

        trace = self._make_trace_for_payload(msg_type, entity, sim_time, data)
        payload["trace"] = trace

        topic = MQTT_TOPICS.get(msg_type, MQTT_TOPICS.get("mcm"))

        # Optional app-level impairments
        if config.APP_TX_DROP_PROB > 0.0 and random.random() < config.APP_TX_DROP_PROB:
            if config.ENABLE_STATS_LOGGING:
                stats_logger.log_message_event(
                    wall_time=time.time(),
                    sim_time=sim_time,
                    direction="drop",
                    topic=topic,
                    msg_type=msg_type,
                    station_id=entity.station_id,
                    receiver_id=self._extract_receiver_id(msg_type, payload),
                    manoeuvre_id=data.get("manoeuvre_id", ""),
                    session_id=trace.get("session_id", ""),
                    message_id=trace.get("message_id", ""),
                    python_tx_wall_time=trace.get("python_tx_wall_time", ""),
                    python_tx_sim_time=trace.get("python_tx_sim_time", ""),
                    delay_ms="",
                    raw_json=payload,
                )
            return

        if config.APP_TX_DELAY_MS > 0:
            time.sleep(config.APP_TX_DELAY_MS / 1000.0)

        mqtt_manager.publish(entity.station_id, msg_type, payload)

        if config.ENABLE_STATS_LOGGING:
            stats_logger.log_message_event(
                wall_time=trace.get("python_tx_wall_time"),
                sim_time=sim_time,
                direction="tx",
                topic=topic,
                msg_type=msg_type,
                station_id=entity.station_id,
                receiver_id=self._extract_receiver_id(msg_type, payload),
                manoeuvre_id=data.get("manoeuvre_id", ""),
                session_id=trace.get("session_id", ""),
                message_id=trace.get("message_id", ""),
                python_tx_wall_time=trace.get("python_tx_wall_time", ""),
                python_tx_sim_time=trace.get("python_tx_sim_time", ""),
                delay_ms="",
                raw_json=payload,
            )

        if config.ENABLE_STATS_LOGGING and msg_type == "mcm_request":
            stats_logger.start_session(
                session_id=trace.get("session_id", ""),
                manoeuvre_id=data.get("manoeuvre_id", ""),
                requester_station_id=entity.station_id,
                request_tx_wall_time=trace.get("python_tx_wall_time"),
                request_tx_sim_time=trace.get("python_tx_sim_time"),
            )    
    def _cleanup_vehicles(self):
        active = set(traci.vehicle.getIDList())
        for vid in list(self.vehicles.keys()):
            if vid not in active:
                del self.vehicles[vid]
                if vid in self.vehicle_trigger_states: del self.vehicle_trigger_states[vid]
    
    def shutdown(self):
        self._running = False

        try:
            traci.close()
        except:
            pass

        mqtt_manager.close_all()

        if config.ENABLE_STATS_LOGGING:
            stats_logger.close(output_dir=config.STATS_OUTPUT_DIR)

def main():
    print("=" * 60)
    print("V2X Simulator - Batch Mode")
    print("=" * 60)

    parser = argparse.ArgumentParser()
    parser.add_argument("--route-file", default=None)
    parser.add_argument("--prefix", default="run")
    parser.add_argument("--nogui", action="store_true")
    args = parser.parse_args()

    if args.nogui:
        config.SUMO_GUI = False

    sim = V2XSimulator(
        route_override=args.route_file,
        output_prefix=args.prefix
    )

    try:
        sim.initialize()
        sim.run()
    except KeyboardInterrupt:
        logger.warning("Manual interrupt received.")
    finally:
        sim.shutdown()


if __name__ == "__main__":
    main()
