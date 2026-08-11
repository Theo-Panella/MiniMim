from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

#====================================================================================
# Modelo do corpo da requisicao.
# O Minimim envia {"log": "<linha>"}; os demais campos sao opcionais.
class LogRecebido(BaseModel):
    servico: str | None = None
    log: str 
#====================================================================================


app = FastAPI(title="Centralizador de Logs", version="1.0.0")


#====================================================================================
# Recepcao dos logs
@app.post("/")
def receber_log(entrada: LogRecebido):
    fila = ''
    momento = datetime.now(timezone.utc).isoformat()

    origem = f"[{entrada.servico or '-'}/{fila}]"
    linha = f"{momento} {origem}"

    print(f"Log recebido: {linha}")

    return {"status": "ok", "recebido_em": momento}
#====================================================================================


#====================================================================================
# Healthcheck simples
@app.get("/")
def healthcheck():
    return {"status": "online", "servico": "Centralizador de Logs"}
#====================================================================================