"""
MCM Termination Message Implementation.
"""
from typing import Dict, Any
from ..base import MessageFactory
from .base import MCMBaseMessage

@MessageFactory.register
class MCMTerminationMessage(MCMBaseMessage):
    """
    Rappresenta un messaggio MCM di tipo TERMINATION (mcmType=4).
    Inviato dall'RSU per chiudere una sessione di manovra.
    """
    
    MESSAGE_TYPE = "mcm_termination"
    MCM_TYPE_ID = MCMBaseMessage.MCM_TYPE_TERMINATION

    def _build_basic_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sovrascrittura per aggiungere executionStatus al basicContainer.
        """
        # Costruiamo il container standard
        container = super()._build_basic_container(data)
        
        # Aggiungiamo il campo specifico per la Termination
        # 2 = Completed (come da tuo esempio jsonl)
        container["executionStatus"] = 2 
        
        return container

    def _build_specific_mcm_container(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Costruisce il terminationContainer (vuoto nel tuo esempio).
        """
        return {
            "terminationContainer": {}
        }