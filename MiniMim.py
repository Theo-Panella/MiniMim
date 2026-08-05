#====================================================================================
import time
import re
import yaml
from collections import deque
from watchdog.events import FileSystemEvent, FileSystemEventHandler,FileModifiedEvent
from watchdog.observers import Observer
#====================================================================================


#====================================================================================
# Variaveis Globais
lista_de_servico = ['Flask']
caminho_de_configuracao = "/Minimim/config.yaml"
caminho_de_log = '/Material/logs_colector.txt'
#====================================================================================


#====================================================================================
# Abre o arquivo de Configuracao e compila para melhor desempenho
# Abre regras individualmente, tem mais processamento na primeira rodagem por compilar
# todas as configurações inicialmente
with open(caminho_de_configuracao, 'r') as arquivo_de_configuracao_puro:
    configuracao = yaml.safe_load(arquivo_de_configuracao_puro)

# Para cada servico gera uma LISTA de regras ja ordenada da mais especifica
# para a mais generica (maior especificidade primeiro), com o padrao compilado.
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
#====================================================================================


#====================================================================================
# Funcao de pre_Filtro
def pre_filter(ultimas_linhas,regras):
    # Pega cada linha da ultima linha lida, default = 1
    for cada_linha in ultimas_linhas:
        linha = cada_linha.strip()

        for servico, regras_do_servico in regras.items():
            if servico not in lista_de_servico:
                continue
            ''' Pega cada serviço e sua lista de regras (ja ordenada da mais
                especifica para a mais generica).
                Cada regra tem: id, padrao (compilado) e especificidade.
                EX: Servico:
                        - {id: IDpadraoA, padrao: <compile>, especificidade: 10}
                        - {id: IDpadraoB, padrao: <compile>, especificidade: 1}
                        ...
            '''
            for regra in regras_do_servico:
                # Verifica se atende o padrao; o primeiro match (mais especifico) vence
                if regra["padrao"].search(linha):
                    envio_para_API(linha, servico, regra["id"])
                    #print(f'Log do servico {servico} e Tipo {regra["id"]} encontrado, aplicando pre-filtro do {servico}: {regra["id"]}')
                    #with open("Material/minimim.txt", "a") as file:
                    #    file.write(linha + "\n")
                    break
# Todo o PRE-FILTRO, precisa de uma função com essa mesma logica,
#====================================================================================

#====================================================================================
# Envio do log para API
def envio_para_API(log, servico, tipo):
    # Aqui você pode implementar a lógica para enviar o log para a API
    # Por exemplo, usando a biblioteca requests para fazer uma requisição POST
    import requests

    url = "http://127.0.0.1:8000"  # Substitua pelo endpoint da sua API
    headers = {"Content-Type": "application/json"}
    data = {"servico": servico,"log": log, "tipo": tipo}  # Você pode ajustar os dados conforme necessário
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Log enviado para centralizador, Status code:{response.status_code}")
        else:
            print(f"Falha ao enviar log. Status code: {response.status_code}")
    except Exception as e:
        print(f"Erro ao enviar log: {e}")


#====================================================================================
# Classe evento do Watchdog
class MyEventHandler(FileSystemEventHandler):
    def __init__(self):
        self._pos = 0          # Posicao inicial (Na primeira vez rodando faz ingestão inicial e depois continua apartir da ultima)

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.src_path == caminho_de_log and event.event_type == "modified":
            #print("Nova tentativa de Login detectada")
            #print("Analisando log...")
            with open(caminho_de_log, "r", encoding="utf-8") as f:
                #ultimas_linhas = deque(f, maxlen=quantidade_de_ultimas_linhas)
                f.seek(self._pos)
                novas_linhas = f.readlines()
                self._pos = f.tell()
                pre_filter(novas_linhas,regras)
#====================================================================================


#====================================================================================
#Chama evento e mantem em loop
if __name__ == "__main__":
    event_handler = MyEventHandler()
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=True)
    observer.start()
    print("Analisando log...")
    try:    
        while True:
            time.sleep(2)
    finally:
        observer.stop()
        observer.join()
#====================================================================================