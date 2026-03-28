"""
Classe base astratta per tutti i messaggi V2X.
Implementa il pattern Factory per creare messaggi.
"""

from abc import ABC, abstractmethod
from typing import Type, Optional
import logging

logger = logging.getLogger(__name__)


class BaseMessage(ABC):
    """
    Classe base astratta per tutti i tipi di messaggio V2X.
    """
    
    # Tipo di messaggio (da sovrascrivere nelle sottoclassi)
    MESSAGE_TYPE: str = "unknown"
    
    def __init__(self, gen_delta_time: int):
        """
        Args:
            gen_delta_time: Timestamp di generazione (ETSI TimestampIts mod 65536)
        """
        self.gen_delta_time = gen_delta_time
    
    @abstractmethod
    def build_payload(self, data: dict) -> dict:
        """
        Costruisce il payload JSON del messaggio.
        
        Args:
            data: Dizionario con i dati dell'entità
            
        Returns:
            Payload JSON pronto per l'invio
        """
        pass
    
    @classmethod
    def get_type(cls) -> str:
        """Restituisce il tipo di messaggio."""
        return cls.MESSAGE_TYPE


class MessageFactory:
    """
    Factory per creare istanze di messaggi.
    Registra automaticamente i tipi di messaggio disponibili.
    """
    
    _registry: dict[str, Type[BaseMessage]] = {}
    
    @classmethod
    def register(cls, message_class: Type[BaseMessage]) -> Type[BaseMessage]:
        """
        Decorator per registrare una classe messaggio.
        
        Uso:
            @MessageFactory.register
            class CAMMessage(BaseMessage):
                MESSAGE_TYPE = "cam"
                ...
        """
        msg_type = message_class.MESSAGE_TYPE
        if msg_type in cls._registry:
            logger.warning(f"Sovrascrittura registrazione per messaggio tipo '{msg_type}'")
        
        cls._registry[msg_type] = message_class
        logger.debug(f"Registrato messaggio tipo '{msg_type}'")
        return message_class
    
    @classmethod
    def create(cls, message_type: str, gen_delta_time: int) -> Optional[BaseMessage]:
        """
        Crea un'istanza di messaggio del tipo specificato.
        
        Args:
            message_type: Tipo di messaggio (es. "cam", "mcm")
            gen_delta_time: Timestamp di generazione
            
        Returns:
            Istanza del messaggio o None se tipo non registrato
        """
        message_class = cls._registry.get(message_type)
        if not message_class:
            logger.error(f"Tipo messaggio '{message_type}' non registrato")
            return None
        
        return message_class(gen_delta_time)
    
    @classmethod
    def get_available_types(cls) -> list[str]:
        """Restituisce la lista dei tipi di messaggio registrati."""
        return list(cls._registry.keys())
    
    @classmethod
    def is_registered(cls, message_type: str) -> bool:
        """Verifica se un tipo di messaggio è registrato."""
        return message_type in cls._registry
