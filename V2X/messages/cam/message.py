"""
CAM Message - Cooperative Awareness Message (ETSI EN 302 637-2).
"""

# from .base import Message, MessageFactory
from ..base import BaseMessage, MessageFactory


@MessageFactory.register
class CAMMessage(BaseMessage):
    """
    Cooperative Awareness Message secondo ETSI EN 302 637-2.
    Supporta sia RSU (statico) che veicoli (dinamico).
    """
    
    MESSAGE_TYPE = "cam"
    
    # Station Types ETSI
    STATION_TYPE_RSU = 15
    STATION_TYPE_OBU = 5
    
    def build_payload(self, data: dict) -> dict:
        """
        Costruisce il payload CAM in base al tipo di stazione.
        
        Args:
            data: Dizionario con chiavi:
                - station_id: int
                - station_type: int (5=car, 15=RSU)
                - lat: float
                - lon: float
                - speed: float (opzionale per RSU)
                - heading: float (opzionale per RSU)
                - acceleration: float (opzionale per RSU)
        """
        station_type = data.get("station_type", self.STATION_TYPE_OBU)
        
        if station_type == self.STATION_TYPE_RSU:
            return self._build_rsu_payload(data)
        else:
            return self._build_vehicle_payload(data)
    
    def _build_rsu_payload(self, data: dict) -> dict:
        """Costruisce payload CAM per RSU (statico)."""
        return {
            "generationDeltaTime": self.gen_delta_time,
            "camParameters": {
                "basicContainer": {
                    "stationType": self.STATION_TYPE_RSU,
                    "referencePosition": self._build_reference_position(data)
                },
                "highFrequencyContainer": {
                    "rsuContainerHighFrequency": {}
                }
            }
        }
    
    def _build_vehicle_payload(self, data: dict) -> dict:
        """Costruisce payload CAM per veicolo (dinamico)."""
        speed = data.get("speed", 0)
        accel = data.get("acceleration", 0)
        
        return {
            "generationDeltaTime": self.gen_delta_time,
            "camParameters": {
                "basicContainer": {
                    "stationType": data.get("station_type", self.STATION_TYPE_OBU),
                    "referencePosition": self._build_reference_position(data)
                },
                "highFrequencyContainer": {
                    "basicVehicleContainerHighFrequency": self._build_hf_container(data)
                },
                "lowFrequencyContainer": {
                    "basicVehicleContainerLowFrequency": self._build_lf_container(data)
                }
            }
        }
    
    def _build_reference_position(self, data: dict) -> dict:
        """Costruisce il blocco referencePosition."""
        return {
            "latitude": data.get("lat", 0),
            "longitude": data.get("lon", 0),
            "positionConfidenceEllipse": {
                "semiMajorAxisLength": 4095,
                "semiMinorAxisLength": 4095,
                "semiMajorAxisOrientation": 3601
            },
            "altitude": {
                "altitudeValue": 800001,
                "altitudeConfidence": 15
            }
        }
    
    def _build_hf_container(self, data: dict) -> dict:
        """Costruisce il High Frequency Container per veicoli."""
        speed = data.get("speed", 0)
        accel = data.get("acceleration", 0)
        heading = data.get("heading", 0)
        
        # da aggiungere controlli sui valori secondo specifica
        # https://github.com/nap-it/vanetza-nap/blob/master/asn1/CDD-Release2.asn
        # es. per length " `n` (`n > 0` and `n < 1022`) to indicate the applicable value n is equal to or 
        # less than n x 0,1 metre, and greater than (n-1) x 0,1 metre"
        length_val = data.get("length", 0)
        width_val = data.get("width", 0)

        drive_dir = 0 if speed >= 0 else 1  # 0=forward, 1=backward (DA RIVEDERE la logica di controllo)
        
        return {
            "heading": {
                "headingValue": heading,
                "headingConfidence": 127
            },
            "speed": {
                "speedValue": speed,
                "speedConfidence": 127
            },
            "driveDirection": drive_dir,
            "vehicleLength": {
                "vehicleLengthValue": length_val,
                "vehicleLengthConfidenceIndication": 4 # noTrailerPresent (0)
            },
            "vehicleWidth": width_val,
            "longitudinalAcceleration": {
                "value": accel,
                "confidence": 102
            },
            "curvature": {
                "curvatureValue": 1023,
                "curvatureConfidence": 7
            },
            "curvatureCalculationMode": 2,
            "yawRate": {
                "yawRateValue": 0,
                "yawRateConfidence": 8
            },
            "accelerationControl": {
                "brakePedalEngaged": accel < -0.5,
                "gasPedalEngaged": accel > 0,
                "emergencyBrakeEngaged": False,
                "collisionWarningEngaged": False,
                "accEngaged": False,
                "cruiseControlEngaged": False,
                "speedLimiterEngaged": False
            },
            "steeringWheelAngle": {
                "steeringWheelAngleValue": 512,
                "steeringWheelAngleConfidence": 127
            }
        }
    
    def _build_lf_container(self, data: dict) -> dict:
        """Costruisce il Low Frequency Container per veicoli."""
        # Recupero lo stato delle luci dal dizionario 'data'
        # Uso .get() con False come default se il dato non viene passato
        left_turn = data.get("light_left_turn", False)
        right_turn = data.get("light_right_turn", False)

        # Creo una stringa leggibile invece di stampare solo se True
        stato_sx = "ACCESA" if left_turn else "SPENTA"
        stato_dx = "ACCESA" if right_turn else "SPENTA"
        
        # Stampa sempre, indicando lo stato
        #print(f"DEBUG CAM [Veicolo {data.get('station_id')}]: SX={stato_sx} | DX={stato_dx}")

        return {
            "vehicleRole": 0,
            "exteriorLights": {
                # Luci anabbaglianti (spesso accese di default in marcia)
                "lowBeamHeadlightsOn": data.get("light_low_beam", True), 
                "highBeamHeadlightsOn": False,
                "leftTurnSignalOn": left_turn,
                "rightTurnSignalOn": right_turn,
                "daytimeRunningLightsOn": False,
                "reverseLightOn": False,
                "fogLightOn": False,
                "parkingLightsOn": False
            },
            "pathHistory": []
        }
