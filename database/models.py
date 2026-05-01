from datetime import datetime
from pydantic import BaseModel

class Chamado(BaseModel):
    id: int = None
    cliente_pergunta: str
    ia_resposta: str
    status: str = "Aberto"
    data_criacao: datetime = datetime.now()