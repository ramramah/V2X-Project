from typing import Dict, Any, List, Optional
from ..base import MessageFactory
from .base import MCMBaseMessage

@MessageFactory.register
class MCMResponseMessage(MCMBaseMessage):
    """
    Rappresenta un messaggio MCM di tipo RESPONSE.
    Inviato dal veicolo (OBU) per accettare o rifiutare una manovra proposta.
    """
    
    # Chiave per la creazione via Factory
    MESSAGE_TYPE = "mcm_response"
    
    # ID numerico per il protocollo (mcmType = 2 -> Response)
    MCM_TYPE_ID = MCMBaseMessage.MCM_TYPE_RESPONSE

    def _build_specific_mcm_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Costruisce l'mcmContainer specifico per la Response.
        Struttura:
        "mcmContainer":{
            "responseContainer":{
                "manouevreResponse": 0,  // accept (0), decline (1)
                "submaneuvres": []       // OPTIONAL
            }
        }
        """
        
        # Recupera il codice di risposta (Default 0 = RESPONSE_ACCEPT)
        response_code = data.get("response_code", self.RESPONSE_ACCEPT)
        
        return {
            "responseContainer": {
                "manouevreResponse": response_code,
                # "declineReason": ... (Opzionale, qui omesso come da richiesta)
                "submaneuvres": [] # Lista vuota come da richiesta
            }
        }