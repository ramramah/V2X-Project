from typing import Optional, List
from .base import Trigger, TriggerResult, TriggerRegistry

@TriggerRegistry.register
class RSUMCMRequestTrigger(Trigger):
    """
    Trigger per RSU: Rileva conflitti e assegna strategie dinamiche.
    """
    MESSAGE_TYPE = "mcm_request"
    
    # Configurazione Trigger
    COOLDOWN_TIME = 5.0   
    DETECTION_RADIUS = 100

    # LISTA DEI VEICOLI GESTITI DA PYTHON (V2X)
    MANAGED_IDS = ["1", "2"] 

    def evaluate(
        self,
        entity_id: str,
        current_time: float,
        current_state: dict,
        previous_state: Optional[dict] = None
    ) -> TriggerResult:
        
        prev_history = previous_state.get("processed_vehicles", {}) if previous_state else {}
        new_history = prev_history.copy()
        
        # Pulizia history
        for vid, timestamp in list(new_history.items()):
            if current_time - timestamp > self.COOLDOWN_TIME:
                del new_history[vid]

        neighbors = current_state.get("neighbors", [])

        # --- FILTRO 1: Consideriamo SOLO i veicoli gestiti (1 e 2) ---
        # Gli altri veicoli (3, 4, etc.) vengono ignorati completamente dal sistema V2X
        # e lasciati alla gestione fisica di SUMO.
        relevant_neighbors = []
        for v in neighbors:
            if v["id"] in self.MANAGED_IDS and v["distance_to_rsu"] <= self.DETECTION_RADIUS:
                relevant_neighbors.append(v)
        

        targets = []
        
        trigger_active = False
        turning_vehicle_id = None

        # 1. RILEVAMENTO: Troviamo chi sta svoltando
        for veh in relevant_neighbors:
            veh_id = veh["id"]
            if veh_id in new_history: continue 
                
            is_turning = veh["light_left_turn"] or veh["light_right_turn"]
            dist = veh["distance_to_rsu"]
            
            if is_turning and dist <= self.DETECTION_RADIUS:
                trigger_active = True
                turning_vehicle_id = veh_id
                break 

        # 2. ASSEGNAZIONE STRATEGIE
        if trigger_active:
            print(f"[Trigger] RSU coordina: Priorità a {turning_vehicle_id}, STOP agli altri.")
            
            for veh in relevant_neighbors:
                vid = veh["id"]
                dist = veh["distance_to_rsu"]
                
                if dist <= self.DETECTION_RADIUS:
                    target_entry = veh.copy()
                    
                    # --- PUNTO CRUCIALE ---
                    if vid == turning_vehicle_id:
                        target_entry["advised_strategy"] = "stayInLane" # VAI
                    else:
                        target_entry["advised_strategy"] = "stop" # FERMATI
                    # ----------------------
                    
                    targets.append(target_entry)
                    new_history[vid] = current_time

        if targets:
            return TriggerResult(
                should_send=True, 
                new_state={
                    "processed_vehicles": new_history,
                    "current_targets": targets 
                },
                reason=f"Coordinating: {turning_vehicle_id} vs Others"
            )
            
        return TriggerResult(False, {"processed_vehicles": new_history})
    
@TriggerRegistry.register
class RSUMCMTerminationTrigger(Trigger):
    """
    Trigger per RSU: Invia MCM Termination quando un veicolo coordinato
    disinserisce l'indicatore direzionale (fronte di discesa).
    """
    MESSAGE_TYPE = "mcm_termination"

    def evaluate(
        self,
        entity_id: str,
        current_time: float,
        current_state: dict,
        previous_state: Optional[dict] = None
    ) -> TriggerResult:
        
        # 1. Recupera gli ID dei veicoli sotto manovra dalla RSU
        active_ids = current_state.get("active_manoeuvre_ids", [])
        if not active_ids:
            return TriggerResult(False)

        # 2. Recupera i dati dei vicini passati dal Main
        neighbors = current_state.get("neighbors", [])
        
        # Recuperiamo la storia dei segnali dal previous_state del trigger stesso
        prev_signals = previous_state.get("signal_history", {}) if previous_state else {}
        new_signal_history = {}

        should_terminate = False
        reason = ""

        # 3. Analisi dei veicoli per rilevare lo spegnimento della freccia
        for veh in neighbors:
            sid = veh["station_id"]
            # Stato attuale: True se almeno una freccia è accesa
            curr_on = veh.get("light_left_turn", False) or veh.get("light_right_turn", False)
            new_signal_history[sid] = curr_on

            # Se il veicolo è tra quelli attivi, controlliamo il cambio di stato
            if sid in active_ids:
                was_on = prev_signals.get(sid, False)
                
                # TRIGGER: Era accesa (was_on=True) e ora è spenta (curr_on=False)
                if was_on and not curr_on:
                    should_terminate = True
                    reason = f"Veicolo {sid} ha completato la manovra (freccia OFF)"
                    break

        # 4. Restituiamo il risultato e salviamo la storia dei segnali
        return TriggerResult(
            should_send=should_terminate,
            new_state={"signal_history": new_signal_history},
            reason=reason
        )