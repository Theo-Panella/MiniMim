import os
from dotenv import load_dotenv
import re
import time

import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


# Variaveis globais
lista_de_servico = ['Flask']

#config = configparser.ConfigParser()
load_dotenv()
#config.read('ConfigurationFiles/paths.conf')
caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
file_name = os.getenv('LOG_FILE_NAME')
log_path = os.getenv('LOG_PATH')
print(log_path)
log_path_completo = log_path + file_name


# Abre o arquivo de configuracao e compila os padroes para melhor desempenho.
# Tem mais processamento na primeira rodagem por compilar todas as regras de uma vez.
with open(caminho_de_configuracao, 'r') as arquivo_de_configuracao_puro:
    configuracao = yaml.safe_load(arquivo_de_configuracao_puro)

# Para cada servico gera uma LISTA de regras ja ordenada da mais especifica
# para a mais generica (maior especificidade primeiro), com o padrao compilado.
# EX: Flask: [{id: padraoA, padrao: <compile>, especificidade: 10},
#             {id: padraoB, padrao: <compile>, especificidade: 1}, ...]
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


def pre_filtro(ultimas_linhas, regras):
    """Classifica cada linha nova lida do log; o primeiro match (mais especifico) vence."""
    for cada_linha in ultimas_linhas:
        linha = cada_linha.strip()

        for servico, regras_do_servico in regras.items():
            if servico not in lista_de_servico:
                continue

            for regra in regras_do_servico:
                if regra["padrao"].search(linha):
                    #envio_para_API(linha, servico, regra["id"])
                    print(f'Log do servico {servico} e Tipo {regra["id"]} encontrado, '
                          f'aplicando pre-filtro do {servico}: {regra["id"]}')
                    break


def envio_para_API(log, servico, tipo):
    """Envia o log classificado para o centralizador."""
    url = "http://127.0.0.1:8000"  # Substitua pelo endpoint da sua API
    headers = {"Content-Type": "application/json"}
    data = {"servico": servico, "log": log, "tipo": tipo}

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Log enviado para centralizador, Status code:{response.status_code}")
        else:
            print(f"Falha ao enviar log. Status code: {response.status_code}")
    except Exception as e:
        print(f"Erro ao enviar log: {e}")


class MyEventHandler(FileSystemEventHandler):
    def __init__(self):
        # Posicao da ultima leitura: na primeira vez faz a ingestao inicial
        # e depois continua a partir de onde parou.
        self._pos = 0

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.src_path == log_path_completo and event.event_type == "modified":
            print("Nova tentativa de Login detectada")

            with open(log_path_completo, "r", encoding="utf-8") as f:
                f.seek(self._pos)
                novas_linhas = f.readlines()
                self._pos = f.tell()
                pre_filtro(novas_linhas, regras)


if __name__ == "__main__":
    event_handler = MyEventHandler()
    observer = Observer()
    observer.schedule(event_handler, log_path, recursive=True)
    observer.start()

    print("Analisando log...")
    try:
        while True:
            time.sleep(2)
    finally:
        observer.stop()
        observer.join()
