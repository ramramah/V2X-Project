"""
Gestore centralizzato delle connessioni MQTT.
"""

import json
import logging
from typing import Optional
import paho.mqtt.client as mqtt
from config import MQTT_PORT, MQTT_KEEPALIVE, STATIONS, MQTT_TOPICS

logger = logging.getLogger(__name__)


class MQTTManager:
    """
    Gestisce le connessioni MQTT verso i vari container Docker.
    Implementa un pattern singleton-like per riutilizzare le connessioni.
    """
    
    def __init__(self):
        self._clients: dict[int, mqtt.Client] = {}
        self._connected: set[int] = set()
        self._missing_stations: set[int] = set()
    
    def get_client(self, station_id: int) -> Optional[mqtt.Client]:
        """
        Recupera o crea un client MQTT per lo specifico StationID.
        """
        if station_id in self._clients and station_id in self._connected:
            return self._clients[station_id]
        
        # --- MODIFICA: Se sappiamo già che manca, ritorniamo None senza loggare ---
        if station_id in self._missing_stations:
            return None
        
        station_config = STATIONS.get(station_id)
        if not station_config:
            # --- MODIFICA: Logghiamo una sola volta e aggiungiamo al set ---
            if station_id not in self._missing_stations:
                logger.warning(f"Station {station_id} non trovata nella configurazione (Warning soppresso per future chiamate)")
                self._missing_stations.add(station_id)
            return None
        
        target_ip = station_config.get("ip")
        if not target_ip:
            if station_id not in self._missing_stations:
                logger.warning(f"IP non configurato per station {station_id}")
                self._missing_stations.add(station_id)
            return None
        
        try:
            client = mqtt.Client(client_id=f"v2x_sim_{station_id}")
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.user_data_set({"station_id": station_id})
            
            client.connect(target_ip, MQTT_PORT, MQTT_KEEPALIVE)
            client.loop_start()
            
            self._clients[station_id] = client
            self._connected.add(station_id)
            
            logger.info(f"Connesso a {target_ip} per station {station_id}")
            return client
            
        except Exception as e:
            logger.error(f"Impossibile connettersi a {target_ip}: {e}")
            return None
    
    def _on_connect(self, client, userdata, flags, rc):
        station_id = userdata.get("station_id", "unknown")
        if rc == 0:
            logger.debug(f"MQTT connesso per station {station_id}")
        else:
            logger.error(f"MQTT connessione fallita per station {station_id}, rc={rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        station_id = userdata.get("station_id", "unknown")
        logger.warning(f"MQTT disconnesso per station {station_id}")
        if station_id in self._connected:
            self._connected.discard(station_id)
    
    def publish(self, station_id: int, message_type: str, payload: dict) -> bool:
        """
        Pubblica un messaggio su un topic specifico.
        
        Args:
            station_id: ID della stazione destinataria
            message_type: Tipo di messaggio (es. "cam", "mcm")
            payload: Dizionario del payload da serializzare
            
        Returns:
            True se pubblicato con successo
        """
        client = self.get_client(station_id)
        if not client:
            return False
        
        topic = MQTT_TOPICS.get(message_type)
        if not topic:
            logger.error(f"Topic non configurato per messaggio tipo '{message_type}'")
            return False
        
        try:
            msg_str = json.dumps(payload, separators=(',', ':'))
            result = client.publish(topic, msg_str)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"Errore pubblicazione MQTT: {e}")
            return False
    
    def close_all(self):
        """Chiude tutte le connessioni MQTT."""
        logger.info("Chiusura connessioni MQTT...")
        for station_id, client in self._clients.items():
            try:
                client.loop_stop()
                client.disconnect()
                logger.debug(f"Disconnesso client station {station_id}")
            except Exception as e:
                logger.error(f"Errore chiusura client {station_id}: {e}")
        
        self._clients.clear()
        self._connected.clear()

    def subscribe(self, station_id: int, topic: str, callback) -> bool:
        """
        Sottoscrive una station a un topic specifico con una callback.
        """
        client = self.get_client(station_id)
        if not client:
            return False
        
        try:
            # Paho MQTT richiede che la callback sia associata al client
            client.subscribe(topic)
            client.message_callback_add(topic, callback)
            logger.info(f"Station {station_id} sottoscritta a {topic}")
            return True
        except Exception as e:
            logger.error(f"Errore sottoscrizione station {station_id}: {e}")
            return False
        
# Istanza globale (singleton)
mqtt_manager = MQTTManager()
