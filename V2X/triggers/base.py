"""
Classe base astratta per i Trigger di messaggi V2X.
I Trigger determinano QUANDO un messaggio deve essere inviato.
"""

from abc import ABC, abstractmethod
from typing import Type, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TriggerResult:
    """Risultato della valutazione di un trigger."""
    
    def __init__(self, should_send: bool, new_state: Optional[dict] = None, reason: str = ""):
        """
        Args:
            should_send: True se il messaggio deve essere inviato
            new_state: Nuovo stato da salvare (se presente)
            reason: Motivo del trigger (per debug)
        """
        self.should_send = should_send
        self.new_state = new_state or {}
        self.reason = reason
    
    def __bool__(self):
        return self.should_send


class Trigger(ABC):
    """
    Classe base astratta per tutti i trigger.
    Un trigger valuta se un messaggio deve essere inviato.
    """
    
    # Tipo di messaggio a cui si applica questo trigger
    MESSAGE_TYPE: str = "unknown"
    
    @abstractmethod
    def evaluate(
        self,
        entity_id: str,
        current_time: float,
        current_state: dict,
        previous_state: Optional[dict] = None
    ) -> TriggerResult:
        """
        Valuta se il messaggio deve essere inviato.
        
        Args:
            entity_id: ID dell'entità (veicolo/RSU)
            current_time: Tempo corrente della simulazione
            current_state: Stato corrente dell'entità
            previous_state: Stato al momento dell'ultimo invio
            
        Returns:
            TriggerResult con decisione e nuovo stato
        """
        pass
    
    @classmethod
    def get_message_type(cls) -> str:
        """Restituisce il tipo di messaggio gestito da questo trigger."""
        return cls.MESSAGE_TYPE


class TriggerRegistry:
    """
    Registry per i trigger disponibili.
    Permette di registrare e recuperare trigger per tipo di messaggio.
    """
    
    _registry: dict[str, Type[Trigger]] = {}
    
    @classmethod
    def register(cls, trigger_class: Type[Trigger]) -> Type[Trigger]:
        """
        Decorator per registrare una classe trigger.
        
        Uso:
            @TriggerRegistry.register
            class ETSICAMTrigger(Trigger):
                MESSAGE_TYPE = "cam"
                ...
        """
        msg_type = trigger_class.MESSAGE_TYPE
        if msg_type in cls._registry:
            logger.warning(f"Sovrascrittura trigger per messaggio '{msg_type}'")
        
        cls._registry[msg_type] = trigger_class
        logger.debug(f"Registrato trigger per messaggio '{msg_type}'")
        return trigger_class
    
    @classmethod
    def get(cls, message_type: str) -> Optional[Trigger]:
        """
        Restituisce un'istanza del trigger per il tipo di messaggio.
        
        Args:
            message_type: Tipo di messaggio (es. "cam", "mcm")
            
        Returns:
            Istanza del trigger o None se non registrato
        """
        trigger_class = cls._registry.get(message_type)
        if not trigger_class:
            logger.warning(f"Nessun trigger registrato per '{message_type}'")
            return None
        
        return trigger_class()
    
    @classmethod
    def get_available_types(cls) -> list[str]:
        """Restituisce i tipi di messaggio con trigger registrati."""
        return list(cls._registry.keys())
