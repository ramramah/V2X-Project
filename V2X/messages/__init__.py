"""
Package messages - Espone la Factory e i tipi di messaggio.
"""

# 1. Importiamo la base
from .base import  MessageFactory, BaseMessage

# 2. Importiamo dai sotto-package. 
# Questo fa scattare l'__init__.py dentro 'cam' e 'mcm', registrando le classi.
from .cam import CAMMessage
from .mcm.intent import MCMIntentMessage  # Importiamo le classi concrete dai sub-package
from .mcm.request import MCMRequestMessage
from .mcm.response import MCMResponseMessage
from .mcm.termination import MCMTerminationMessage

__all__ = ["BaseMessage", "MessageFactory", "CAMMessage", "MCMIntentMessage", "MCMRequestMessage", "MCMResponseMessage", "MCMTerminationMessage"]