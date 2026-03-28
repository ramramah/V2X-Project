"""
ETSI CAM Trigger - Logica di triggering secondo ETSI EN 302 637-2.
"""

from typing import Optional
import logging

from .base import Trigger, TriggerResult, TriggerRegistry
from config import CAM_TRIGGER_CONFIG
from utils import euclidean_distance, heading_difference

logger = logging.getLogger(__name__)


@TriggerRegistry.register
class ETSICAMTrigger(Trigger):
    """
    Trigger per CAM secondo specifica ETSI EN 302 637-2.
    
    Implementa la logica T_GenCam dinamica:
    - T_GenCamMin: 100ms (intervallo minimo assoluto)
    - T_GenCamMax: 1000ms (intervallo massimo in condizioni statiche)
    - Trigger dinamici basati su variazione di posizione, velocità, heading
    - N_GenCam: persistenza della frequenza elevata
    """
    
    MESSAGE_TYPE = "cam"
    
    def __init__(self):
        # Carica configurazione
        self.t_gen_cam_min = CAM_TRIGGER_CONFIG.get("t_gen_cam_min", 0.1)
        self.t_gen_cam_max = CAM_TRIGGER_CONFIG.get("t_gen_cam_max", 1.0)
        self.n_gen_cam_default = CAM_TRIGGER_CONFIG.get("n_gen_cam_default", 3)
        
        self.delta_pos_threshold = CAM_TRIGGER_CONFIG.get("delta_pos_threshold", 4.0)
        self.delta_speed_threshold = CAM_TRIGGER_CONFIG.get("delta_speed_threshold", 0.5)
        self.delta_heading_threshold = CAM_TRIGGER_CONFIG.get("delta_heading_threshold", 4.0)
    
    def evaluate(
        self,
        entity_id: str,
        current_time: float,
        current_state: dict,
        previous_state: Optional[dict] = None
    ) -> TriggerResult:
        """
        Valuta se inviare un CAM secondo le regole ETSI.
        
        Args:
            entity_id: ID del veicolo
            current_time: Tempo simulazione corrente
            current_state: Dict con x, y, speed, heading
            previous_state: Stato al momento dell'ultimo CAM inviato
            
        Returns:
            TriggerResult con decisione e nuovo stato trigger
        """
        
        # CASO 1: Primo invio assoluto
        if previous_state is None:
            return TriggerResult(
                should_send=True,
                new_state={
                    "time": current_time,
                    "x": current_state["x"],
                    "y": current_state["y"],
                    "speed": current_state["speed"],
                    "heading": current_state["heading"],
                    "t_gen_cam": self.t_gen_cam_max,
                    "n_gen_cam": self.n_gen_cam_default,
                },
                reason="first_message"
            )
        
        # Calcola tempo trascorso
        dt = current_time - previous_state.get("time", 0)
        
        # BLOCCO: T_GenCamMin non ancora trascorso
        if dt < self.t_gen_cam_min - 0.005:  # Tolleranza per float
            return TriggerResult(
                should_send=False,
                reason="min_interval_not_elapsed"
            )
        
        # Recupera stato protocollo corrente
        current_t_gen_cam = previous_state.get("t_gen_cam", self.t_gen_cam_max)
        current_n_gen_cam = previous_state.get("n_gen_cam", self.n_gen_cam_default)
        
        # Calcola delta rispetto all'ultimo invio
        delta_pos = euclidean_distance(
            current_state["x"], current_state["y"],
            previous_state["x"], previous_state["y"]
        )
        delta_speed = abs(current_state["speed"] - previous_state["speed"])
        delta_heading = heading_difference(
            current_state["heading"], previous_state["heading"]
        )
        
        # Verifica trigger dinamici
        is_dynamic_trigger = (
            delta_pos > self.delta_pos_threshold or
            delta_speed > self.delta_speed_threshold or
            delta_heading > self.delta_heading_threshold
        )
        
        # Prepara nuovo stato
        new_t_gen_cam = current_t_gen_cam
        new_n_gen_cam = current_n_gen_cam
        
        should_send = False
        reason = ""
        
        # CONDIZIONE 1: Trigger dinamico
        if is_dynamic_trigger:
            should_send = True
            new_t_gen_cam = dt  # Adatta intervallo al tempo trascorso
            new_n_gen_cam = self.n_gen_cam_default  # Ricarica contatore
            reason = f"dynamic_trigger(pos={delta_pos:.2f}, spd={delta_speed:.2f}, hdg={delta_heading:.2f})"
        
        # CONDIZIONE 2: Timeout intervallo corrente
        elif dt >= current_t_gen_cam:
            should_send = True
            
            if current_n_gen_cam > 0:
                new_n_gen_cam = current_n_gen_cam - 1
            
            # Se contatore esaurito, torna a frequenza lenta
            if new_n_gen_cam == 0:
                new_t_gen_cam = self.t_gen_cam_max
            
            reason = f"interval_timeout(t_gen={current_t_gen_cam:.2f}, n_gen={current_n_gen_cam})"
        
        # Costruisci nuovo stato solo se invio
        if should_send:
            new_state = {
                "time": current_time,
                "x": current_state["x"],
                "y": current_state["y"],
                "speed": current_state["speed"],
                "heading": current_state["heading"],
                "t_gen_cam": new_t_gen_cam,
                "n_gen_cam": new_n_gen_cam,
            }
        else:
            new_state = None
            reason = "no_trigger"
        
        return TriggerResult(
            should_send=should_send,
            new_state=new_state,
            reason=reason
        )


# Template per aggiungere nuovi trigger:
#
# @TriggerRegistry.register
# class MCMTrigger(Trigger):
#     """Trigger per MCM messages."""
#     
#     MESSAGE_TYPE = "mcm"
#     
#     def evaluate(self, entity_id, current_time, current_state, previous_state):
#         # Logica specifica per MCM
#         # Es: invia quando c'è una manovra pianificata
#         if current_state.get("has_planned_maneuver"):
#             return TriggerResult(should_send=True, reason="planned_maneuver")
#         return TriggerResult(should_send=False)
