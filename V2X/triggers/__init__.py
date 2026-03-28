"""
Package triggers - Contiene le logiche di triggering per i messaggi V2X.
"""

from .base import Trigger, TriggerRegistry
from .etsi_cam_trigger import ETSICAMTrigger

__all__ = ["Trigger", "TriggerRegistry", "ETSICAMTrigger"]
