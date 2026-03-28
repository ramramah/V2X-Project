# Importa la classe base dal file base.py presente in questa cartella
from .base import MCMBaseMessage

# Importa i file specifici per far scattare la registrazione (opzionale ora, ma fondamentale per la Factory)
from .intent import MCMIntentMessage
from .request import MCMRequestMessage
from .response import MCMResponseMessage
from .termination import MCMTerminationMessage
# ... aggiungi gli altri man mano che li crei

#__all__ = ["MCMMessage", "MCMIntent", "MCMRequest"]
__all__ = ["MCMMessage", "MCMIntent", "MCMRequest", "MCMResponse", "MCMTermination"]