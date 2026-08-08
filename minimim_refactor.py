import os
from dotenv import load_dotenv
import re
import time
import json

import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

load_dotenv()
caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
padrao_split = os.getenv('PADRAO_SPLIT')
log_path = os.getenv('LOG_PATH').split(',')
path_arquivo_json = "ConfigurationFiles/relacao_pos_file.json"

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

def pre_filtro(ultimas_linhas, regras, servico_do_evento):
    """Classifica cada linha nova lida do log; o primeiro match (mais especifico) vence."""
    try:
        regras_do_servico = regras.get(servico_do_evento)
        if regras_do_servico is None:
            return              
        for cada_linha in ultimas_linhas:
            linha = cada_linha.strip()
            for regra in regras_do_servico:
                if regra["padrao"].search(linha):
                    break
                else:
                    pass
    except Exception:
        print("Deu erro, corre aqui")
        pass
    


def popula_indice(evento):
    if evento not in relacao_pos_file:
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
            if ultima_quebra == -1:
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
            #print(relacao_pos_file)
            
                        
    except (PermissionError, IOError):
        #Ocorre se o arquivo estiver aberto por outro processo de escrita
        print("O arquivo está em uso ou sendo escrito no momento. Nenhuma leitura foi feita.")
        pass

    
def cria_observer():
    event_handler = MyEventHandler()
    observer = Observer()

    for each in log_path:
        observer.schedule(event_handler, each, recursive=False)

    observer.start()

    print("Analisando log...")
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


if __name__ == "__main__":
    cria_observer()