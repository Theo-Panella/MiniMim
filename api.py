from datetime import datetime, timezone

from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError

#====================================================================================
# Modelo do corpo da requisicao.
# O Minimim envia {"log": "<linha>"}; os demais campos sao opcionais.
class LogRecebido(BaseModel):
    servico: str | None = None
    log: str
    regra: str
#====================================================================================


app = Flask(__name__)


#====================================================================================
# Recepcao dos logs
# O Flask nao injeta o corpo pelo type hint: e preciso ler e validar na mao.
@app.post("/")
def receber_log():
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        return jsonify({"status": "erro", "detalhe": "corpo deve ser um objeto JSON"}), 400

    try:
        entrada = LogRecebido.model_validate(corpo)
    except ValidationError as erro:
        detalhe = erro.errors(include_url=False, include_context=False)
        return jsonify({"status": "erro", "detalhe": detalhe}), 400

    momento = datetime.now(timezone.utc).isoformat()
    origem = f"[{entrada.servico or '-'}]"
    linha = f"{momento} {origem} {entrada.servico} {entrada.regra}"

    print(f"Log recebido: {linha}")

    return jsonify({"status": "ok", "recebido_em": momento})
#====================================================================================


#====================================================================================
# Healthcheck simples
@app.get("/")
def healthcheck():
    return jsonify({"status": "online", "servico": "Centralizador de Logs"})
#====================================================================================


if __name__ == "__main__":
    # A porta 8000 e a que o MiniMim usa em envio_para_API.
    app.run(host="127.0.0.1", port=8000, debug=True)
