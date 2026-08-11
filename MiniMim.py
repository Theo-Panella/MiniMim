import os
from dotenv import load_dotenv
import re
import time
import json
import logging
import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

load_dotenv()
caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
log_path = os.getenv('LOG_PATH').split(',')
path_arquivo_json = os.getenv('JSON_PATH')
log_from_logging = logging.getLogger(__name__)

# Abre o arquivo de configuracao e compila os padroes para melhor desempenho.
# Tem mais processamento na primeira rodagem por compilar todas as regras de uma vez.
with open(caminho_de_configuracao, 'r') as arquivo_de_configuracao_puro:
    configuracao = yaml.safe_load(arquivo_de_configuracao_puro)

with open(path_arquivo_json, 'r') as arquivo_json:
    relacao_pos_file = json.load(arquivo_json)

regras = {
    servico: sorted(
        [
            {
                "id": id_padrao,
                "padrao": re.compile(regra["padrao"]),
                "especificidade": regra.get("especificidade", 0),
            }
            for id_padrao, regra in padroes.items()
        ],
        key=lambda r: -r["especificidade"],
    )
    for servico, padroes in configuracao.items()
}


def cria_observer():
    event_handler = MyEventHandler()
    observer = Observer()

    for each in log_path:
        observer.schedule(event_handler, each, recursive=False)

    observer.start()

    print("Observando...")
    try:
        while True:
            time.sleep(2)
    finally:
        print("Acabou")
        observer.stop()
        observer.join()


class MyEventHandler(FileSystemEventHandler):
    def __init__(self):
        # Posicao da ultima leitura: na primeira vez faz a ingestao inicial
        # e depois continua a partir de onde parou.
        self._pos = 0
        
    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type == "modified" and not event.is_directory:
            popula_indice(event.src_path)


def popula_indice(evento):
    if evento not in relacao_pos_file or os.path.getsize(evento) < relacao_pos_file[evento]:
        relacao_pos_file[evento] = 0
        ler_arquivo(evento)
    else:
        ler_arquivo(evento)

def ler_arquivo(evento):
    try:
        with open(evento, "rb") as file:
            pos_inicial = relacao_pos_file[evento]
            file.seek(pos_inicial)
            #print(pos_inicial)
            conteudo = file.read()

            ultima_quebra = conteudo.rfind(b"\n")
            if ultima_quebra == -1 and pos_inicial != 0:
                # ainda nao ha nenhuma linha completa, espera o proximo evento
                return

            completo = conteudo[:ultima_quebra + 1]
            novas_linhas = completo.decode("utf-8").splitlines()
            
            # Reposiciona exatamente no fim da ultima linha completa.
            # seek() em modo texto so aceita posicoes vindas de tell(),
            # entao relemos so o trecho completo para obter uma posicao valida.
            relacao_pos_file[evento] = pos_inicial + len(completo)
            servico_do_evento = os.path.basename(os.path.dirname(evento))
            json.dump(relacao_pos_file,open(path_arquivo_json,"w"))
            pre_filtro(novas_linhas, regras, servico_do_evento)
                              
    except Exception:
        log_from_logging.exception("falha no pre_filtro, servico=%s", servico_do_evento)

def pre_filtro(ultimas_linhas, regras, servico_do_evento):
    """Classifica cada linha nova lida do log; o primeiro match (mais especifico) vence."""
    try:
        print("Chegou no Pre filtro")
        regras_do_servico = regras.get(servico_do_evento)
        if regras_do_servico is None:
            return              
        for cada_linha in ultimas_linhas:
            linha = cada_linha.strip()
            for regra in regras_do_servico:
                if regra["padrao"].search(linha):
                    envio_para_API(linha,servico_do_evento)
                    break
                else:
                    pass
    except Exception:
        log_from_logging.exception("falha no pre_filtro, servico=%s", servico_do_evento)

def envio_para_API(log, servico):
    """Envia o log classificado para o centralizador."""
    url = "http://127.0.0.1:8000"  # Substitua pelo endpoint da sua API
    headers = {"Content-Type": "application/json"}
    data = {"servico": servico, "log": log}

    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"Log enviado para centralizador, Status code: {response.status_code}")
        else:
            print(f"Falha ao enviar log_from_logging Status code: {response.status_code}")
    except requests.exceptions.RequestException:
        log_from_logging.exception("Erro ao enviar log para o centralizador")

def read_from_last(evento):
    if os.path.getsize(evento) < relacao_pos_file[evento]:
        relacao_pos_file[evento] = os.path.getsize(evento)
        ler_arquivo(evento)

if __name__ == "__main__":
    cria_observer()