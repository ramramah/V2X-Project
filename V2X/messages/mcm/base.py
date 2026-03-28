"""
Classe base per tutti i messaggi MCM (Manoeuvre Coordination Message).
Gestisce il Basic Container comune e le costanti ETSI.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Import relativo per risalire a messages/base.py
# messages/mcm/base.py -> (..) messages/ -> (...) v2x_simulator/ -> messages/base.py
# Nota: Dato che messages è un package, l'import corretto verso il genitore è:
from ..base import BaseMessage

class MCMBaseMessage(BaseMessage):
    """
    Classe astratta intermedia per messaggi MCM.
    Estende BaseMessage implementando il BasicContainer standard per MCM.
    """

    # ==========================================
    # Costanti MCM (Condivise da tutte le sottoclassi)
    # ==========================================
    
    # Questo ID numerico deve essere sovrascritto dalle sottoclassi (es. Intent=0, Request=1)
    MCM_TYPE_ID: int = -1 

    # MCM Types
    MCM_TYPE_INTENT = 0
    MCM_TYPE_REQUEST = 1
    MCM_TYPE_RESPONSE = 2
    MCM_TYPE_RESERVATION = 3
    MCM_TYPE_TERMINATION = 4
    MCM_TYPE_CANCELLATION_REQUEST = 5
    MCM_TYPE_EMERGENCY_MANOEUVRE_RESERVATION = 6
    MCM_TYPE_EXECUTION_STATUS = 7
    MCM_TYPE_OFFER = 8
    MCM_TYPE_ACKNOWLEDGMENT = 9

    # Station Types
    STATION_TYPE_OBU = 1  
    STATION_TYPE_RSU = 2

    # ITSS Roles
    ITSS_ROLE_NOT_AVAILABLE = 0
    ITSS_ROLE_COORDINATING_ITSS = 1
    ITSS_ROLE_NOT_COORDINATING_SUBJECT_VEHICLE = 2
    ITSS_ROLE_TARGET_VEHICLE = 3

    # Concept
    MANOEUVRE_COORD_CONCEPT = 0 # agreementSeeking(0)

    # Execution Status
    EXEC_STATUS_STARTED = 0
    EXEC_STATUS_IN_PROGRESS = 1
    EXEC_STATUS_COMPLETED = 2
    EXEC_STATUS_TERMINATED = 3
    EXEC_STATUS_CHAINED = 4

    # Response types
    RESPONSE_ACCEPT = 0
    RESPONSE_DECLINE = 1

    # Manoeuvre Overall Strategy
    STRATEGY_UNDEFINED = "undefined"
    STRATEGY_TRANSIT_TO_HUMAN = "transitToHumanDrivenMode"
    STRATEGY_TRANSIT_TO_AUTO = "transitToAutomatedDrivingMode"
    STRATEGY_DRIVE_STRAIGHT = "driveStraight"
    STRATEGY_TURN_LEFT = "turnLeft"
    STRATEGY_TURN_RIGHT = "turnRight"
    STRATEGY_U_TURN = "uTurn"
    STRATEGY_MOVE_BACKWARD = "moveBackward"
    STRATEGY_OVERTAKE = "overtake"
    STRATEGY_ACCELERATE = "accelerate"
    STRATEGY_SLOWDOWN = "slowdown"
    STRATEGY_STOP = "stop"
    STRATEGY_GO_TO_LEFT_LANE = "goToLeftLane"
    STRATEGY_GO_TO_RIGHT_LANE = "oToRightLane" # in MCM-PDU-Description.asn c'è un errore di battitura: "oToRightLane"
    STRATEGY_GET_ON_HIGHWAY = "getOnHighway"
    STRATEGY_EXIT_HIGHWAY = "exitHighway"
    STRATEGY_TAKE_TOLLING_LANE = "takeTollingLane" # Richiede un intero
    STRATEGY_STOP_AND_WAIT = "stopAndWait"
    STRATEGY_EMERGENCY_BRAKE = "emergencyBrakeAndStop"
    STRATEGY_RESET_STOP = "resetStopAndRestartMoving"
    STRATEGY_STAY_IN_LANE = "stayInLane"
    STRATEGY_RESET_STAY_IN_LANE = "resetStayInLane"
    STRATEGY_STAY_AWAY = "stayAway"
    STRATEGY_RESET_STAY_AWAY = "resetStayAway"
    STRATEGY_FOLLOW_ME = "followMe"
    STRATEGY_EXISTING_GROUP = "existingGroup"
    STRATEGY_DISBAND_GROUP = "temporarilyDisbandAnExistingGroup"
    STRATEGY_CONSTITUTE_GROUP = "constituteAtemporarilyGroup"
    STRATEGY_DISBAND_TEMP_GROUP = "disbandATemporarilyGroup"

    def build_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implementazione del metodo astratto di BaseMessage.
        Definisce lo scheletro fisso di un messaggio MCM.
        """
        return {
            "basicContainer": self._build_basic_container(data),
            "mcmContainer": self._build_specific_mcm_container(data)
        }

    def _build_basic_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Costruisce il basicContainer comune.
        Gestisce il campo 'rational' come opzionale.
        """
        station_type = data.get("station_type", self.STATION_TYPE_OBU)
        
        # Logica Posizione
        lat = data.get("lat", 0)
        lon = data.get("lon", 0)
        
        if station_type == self.STATION_TYPE_RSU:
            lat = data.get("lat", 900000001) 
            lon = data.get("lon", 1800000001)

        # 1. Creiamo il dizionario base con i campi OBBLIGATORI
        basic_container = {
            "generationDeltaTime": self.gen_delta_time,
            "stationID": data.get("station_id", 0),
            "stationType": station_type,
            "itssRole": data.get("itss_role", self.ITSS_ROLE_NOT_AVAILABLE), 
            "position": {
                "latitude": lat,
                "longitude": lon,
                "positionConfidenceEllipse": {
                    "semiMajorAxisLength": 4095,
                    "semiMinorAxisLength": 4095,
                    "semiMajorAxisOrientation": 3601
                },
                "altitude": {
                    "altitudeValue": 800001,
                    "altitudeConfidence": 15
                }
            },
            "mcmType": self.MCM_TYPE_ID, 
            "manoeuvreId": data.get("manoeuvre_id", 0),
            "concept": self.MANOEUVRE_COORD_CONCEPT
        }

        # 2. Gestione campo OPTIONAL 'rational'
        # Lo aggiungiamo SOLO se nel dizionario 'data' è presente la chiave "cost"
        if "cost" in data:
            basic_container["rational"] = {
                "manoeuvreCooperationCost": data["cost"]
            }

        return basic_container

    def _build_strategy_payload(self, strategy_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        HELPER METHOD: Costruisce il payload della strategia.
        Gestisce la differenza tra strategie NULL (es. driveStraight) 
        e strategie con VALORE (es. takeTollingLane).
        """
        
        # Caso speciale: takeTollingLane richiede un numero (INTEGER 1..31)
        if strategy_key == self.STRATEGY_TAKE_TOLLING_LANE:
            lane_number = data.get("lane_number", 1) # Default 1 se manca
            return { strategy_key: lane_number }
            
        # Tutti gli altri casi sono NULL (in Python None)
        return { strategy_key: None }

    @abstractmethod
    def _build_specific_mcm_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Metodo astratto: le sottoclassi (Intent, Request) DEVONO implementare 
        questo metodo per riempire il contenuto specifico del messaggio.
        """
        pass