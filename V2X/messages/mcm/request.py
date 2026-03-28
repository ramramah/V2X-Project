from typing import Dict, Any, List, Optional
from ..base import MessageFactory
from .base import MCMBaseMessage

@MessageFactory.register
class MCMRequestMessage(MCMBaseMessage):
    """
    Rappresenta un messaggio MCM di tipo REQUEST (Agreement Seeking).
    Utilizzato da un veicolo o RSU per proporre manovre a uno o più attori (executants).
    
    Struttura dati attesa in 'data':
    {
        "station_id": int,
        "station_type": int,
        "manoeuvre_id": int,
        "cost": int (opzionale),
        "executants": [
            {
                "executant_id": int,
                "advised_strategy": str (es. "stayInLane", opzionale),
                "lane_number": int (opzionale, se richiesto dalla strategia),
                "submanoeuvres": [
                    {
                        "submanoeuvre_id": int,
                        "trajectory": { ... } (opzionale)
                    }
                ]
            },
            ...
        ]
    }
    """
    
    # Chiave per la creazione via Factory
    MESSAGE_TYPE = "mcm_request"
    
    # ID numerico per il protocollo (mcmType = 1 -> Request/Agreement Seeking)
    MCM_TYPE_ID = MCMBaseMessage.MCM_TYPE_REQUEST 

    def _build_specific_mcm_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Costruisce l'mcmContainer specifico per la Request, gestendo una lista
        di executants come definito nel JSONL.
        """
        
        # Estraiamo la lista degli executants dal dizionario 'data'
        executants_data = data.get("executants", [])
        
        advised_manoeuvre_container = []

        for entry in executants_data:
            # 1. Costruzione del blocco per il singolo Executant
            # Nota: nel JSONL la chiave è "submaneuvres" (senza 'o'), manteniamo la compatibilità
            executant_payload = {
                "executantID": entry.get("executant_id"),
                "submaneuvres": self._build_submanoeuvres(entry.get("submanoeuvres", []))
            }

            # 2. Gestione opzionale di currentStateAdvisedChange (es. Strategy)
            # Usiamo il metodo helper della classe base per formattare correttamente la strategia
            # es. strategy_key="stayInLane" -> {"stayInLane": None}
            strategy_key = entry.get("advised_strategy")
            if strategy_key:
                executant_payload["currentStateAdvisedChange"] = self._build_strategy_payload(
                    strategy_key, 
                    entry # Passiamo entry per eventuali parametri extra (es. lane_number)
                )
            
            # Supporto fallback per dizionario grezzo se fornito direttamente come 'advised_change'
            elif "advised_change" in entry:
                executant_payload["currentStateAdvisedChange"] = entry["advised_change"]

            advised_manoeuvre_container.append(executant_payload)

        return {
            "advisedManoeuvreContainer": advised_manoeuvre_container
        }

    def _build_submanoeuvres(self, sub_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Helper per costruire la lista delle submanoeuvres per ogni executant.
        """
        submanoeuvres_payload = []
        
        for sub in sub_list:
            sub_item = {
                "submanoeuvreId": sub.get("submanoeuvre_id", 1)
            }
            
            # Gestione opzionale di advisedTrajectory
            # Richiesto se presenti waypoints o speed specifici
            if "trajectory" in sub:
                traj = sub["trajectory"]
                sub_item["advisedTrajectory"] = {
                    "wayPointType": traj.get("way_point_type", 1), # Default 1
                    "wayPoints": [
                        {
                            "pathPosition": {
                                "deltaLatitude": wp.get("delta_lat", 0),
                                "deltaLongitude": wp.get("delta_lon", 0),
                                "deltaAltitude": wp.get("delta_alt", 0)
                            }
                        } for wp in traj.get("way_points", [])
                    ],
                    "speed": [
                        {
                            "speedValue": s.get("value", 16383), # 16383 = unavailable/standstill
                            "speedConfidence": s.get("confidence", 1)
                        } for s in traj.get("speed", [])
                    ]
                }
            
            submanoeuvres_payload.append(sub_item)
            
        return submanoeuvres_payload