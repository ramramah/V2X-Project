"""
Classe base astratta per tutte le entità V2X (RSU, Veicoli, etc.).
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Entity(ABC):
    """
    Classe base per tutte le entità nella simulazione V2X.
    Ogni entità ha un ID, una posizione e può inviare messaggi.
    """
    
    def __init__(self, station_id: int, name: Optional[str] = None):
        """
        Args:
            station_id: ID univoco della stazione (ETSI StationID)
            name: Nome descrittivo opzionale
        """
        self.station_id = station_id
        self.name = name or f"Entity_{station_id}"
        self.enabled_messages: list[str] = []
        
        # Stato corrente
        self._x: float = 0.0
        self._y: float = 0.0
        self._lat: float = 0.0
        self._lon: float = 0.0
        
        logger.debug(f"Creata entità {self.name} (ID: {station_id})")
    
    @property
    def position(self) -> tuple[float, float]:
        """Posizione corrente (x, y) in coordinate SUMO."""
        return self._x, self._y
    
    @property
    def geo_position(self) -> tuple[float, float]:
        """Posizione corrente (lat, lon)."""
        return self._lat, self._lon
    
    @abstractmethod
    def update(self, sim_time: float, **kwargs) -> None:
        """
        Aggiorna lo stato dell'entità.
        Chiamato ad ogni step della simulazione.
        
        Args:
            sim_time: Tempo corrente della simulazione
            **kwargs: Dati aggiuntivi specifici per tipo
        """
        pass
    
    @abstractmethod
    def should_send_message(self, message_type: str, sim_time: float) -> bool:
        """
        Verifica se l'entità deve inviare un messaggio di un certo tipo.
        
        Args:
            message_type: Tipo di messaggio (es. "cam", "mcm")
            sim_time: Tempo corrente della simulazione
            
        Returns:
            True se il messaggio deve essere inviato
        """
        pass
    
    @abstractmethod
    def get_message_data(self, message_type: str) -> dict:
        """
        Restituisce i dati necessari per costruire un messaggio.
        
        Args:
            message_type: Tipo di messaggio
            
        Returns:
            Dizionario con i dati per il messaggio
        """
        pass
    
    def is_message_enabled(self, message_type: str) -> bool:
        """Verifica se un tipo di messaggio è abilitato per questa entità."""
        return message_type in self.enabled_messages
    
    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.station_id}, name='{self.name}')"
