from typing import Dict, Any
# Importiamo la Factory dal livello base generale
from ..base import MessageFactory
# Importiamo la classe base specifica MCM (fratello di questo file)
from .base import MCMBaseMessage

@MessageFactory.register
class MCMIntentMessage(MCMBaseMessage):
    """
    Rappresenta un messaggio MCM di tipo INTENT (Agreement Seeking).
    Utilizzato da un veicolo per proporre una manovra agli altri.
    """
    
    # Chiave per la creazione via Factory
    MESSAGE_TYPE = "mcm_intent"
    
    # ID numerico per il protocollo (va nel JSON -> mcmType)
    # 0 = Intent (Agreement Seeking)
    MCM_TYPE_ID = MCMBaseMessage.MCM_TYPE_INTENT 

    def _build_specific_mcm_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Costruisce il payload specifico per l'Intent: 'vehicleManoeuvreContainer'.
        
        Args:
            data: Dizionario contenente i dati del veicolo (da TRACI/SUMO).
                  Chiavi attese: speed, heading, length, width, strategy, submaneuvres.
        """
        
        # 1. Recupero dati con valori di default (ETSI "Unavailable")
        # speed: cm/s, 16383 = unavailable
        speed_val = data.get("speed", 16383)   
        
        # heading: 0.1 gradi, 3601 = unavailable
        heading_val = data.get("heading", 3601) 
        
        # dimensioni: decimetri (es. 50 = 5 metri)
        length_val = data.get("length", 50)     
        width_val = data.get("width", 20)       
        
        # 2. Gestione Strategy dinamica
        # Il JSON richiede: "manoeuvreOverallStrategy": { "driveStraight": null }
        # Python converte 'None' in 'null'.
        strategy_key = data.get("strategy", "driveStraight")
        strategy_payload = {strategy_key: None}

        # 3. Costruzione della struttura annidata
        return {
            "vehicleManoeuvreContainer": {
                "vehicleCurrentStateContainer": {
                    "vehicleSpeed": {
                        "speedValue": speed_val,
                        "speedConfidence": 1  # Fisso o da parametrizzare se serve
                    },
                    "vehicleHeading": {
                        "value": heading_val,
                        "confidence": 127
                    },
                    "vehicleSize": {
                        "vehicleType": 1, # 1 = Passenger Car
                        # Nota: manteniamo il nome "vehicleLenth" come da tuo schema JSON
                        "vehicleLenth": { 
                            "vehicleLengthValue": length_val,
                            "vehicleLengthConfidenceIndication": 0 # 0 = NoTrailer
                        },
                        "vehicleWidth": width_val,
                        "vehicleHeight": 127 # Unavailable
                    },
                    "manoeuvreOverallStrategy": strategy_payload
                },
                # Lista di sottomanovre (opzionale, default vuota)
                "submaneuvres": data.get("submaneuvres", []) 
            }
        }