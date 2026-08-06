import os
from dotenv import load_dotenv
import re
import time

import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


# Variaveis globais
lista_de_servico = ['Apache']

load_dotenv()
caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
padrao_split = os.getenv('PADRAO_SPLIT')
log_file = os.getenv('LOG_FILE')
log_path = os.getenv('LOG_PATH').split(',')
global_path = os.getenv('GLOBAL_PATH')




# Abre o arquivo de configuracao e compila os padroes para melhor desempenho.
# Tem mais processamento na primeira rodagem por compilar todas as regras de uma vez.
with open(caminho_de_configuracao, 'r') as arquivo_de_configuracao_puro:
    configuracao = yaml.safe_load(arquivo_de_configuracao_puro)
    
relacao_pos_file = {}

class MyEventHandler(FileSystemEventHandler):
    def __init__(self):
        # Posicao da ultima leitura: na primeira vez faz a ingestao inicial
        # e depois continua a partir de onde parou.
        self._pos = 0

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type == "modified":
            print(f"Teve evento no {event.src_path}")
            with open(event.src_path, "r", encoding="utf-8") as file:
                # Procura a ultima linha lida
                file.seek(relacao_pos_file[event.src_path])
                # Le as linhas adicionais
                novas_linhas = file.readlines()
                # Diz a ultima linha lida
                self._pos = file.tell()

                relacao_pos_file[event.src_path] = [self._pos]

                # Printa a posicao de leitura
                print(relacao_pos_file)
                #print(relacao_pos_file)


if __name__ == "__main__":
    event_handler = MyEventHandler()
    observer = Observer()

    for each in log_path:
        observer.schedule(event_handler, each, recursive=False)
        relacao_pos_file[each] = {}

    observer.start()

    print("Analisando log...")
    try:
        while True:
            time.sleep(2)
    finally:
        print("Acabou")
        observer.stop()
        observer.join()
