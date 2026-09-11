import os
from dotenv import load_dotenv
import re
import time
import json
import logging
import requests
import yaml
import threading
import portalocker
import tempfile
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

load_dotenv()

VARIAVEIS_DE_AMBIENTE = [os.getenv('CONFIGURATION_FILE'), os.getenv('LOG_PATH'),
                         os.getenv('STATE_DIR'), os.getenv('API_URL'), os.getenv('STATE_FILE')]

# Checar variaveis de ambiente
if not all(VARIAVEIS_DE_AMBIENTE):
    print("Erro ao iniciar MiniMim, configure o ambiente usando minicli -t")
    raise SystemExit()

caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
log_path = os.getenv('LOG_PATH').split(',')
diretorio_de_estado = os.getenv('STATE_DIR')
arquivo_de_estado = os.getenv('STATE_FILE')
log_from_logging = logging.getLogger(__name__)
url = os.getenv('API_URL')
qtd = 0
batch_de_logs = {}
ultimo_envio = time.monotonic()
lock = threading.Lock()

# Fecha o lote por tamanho; o que sobrar sai por tempo no --observe.
TAMANHO_DO_LOTE = 100
INTERVALO_DE_ENVIO = 5.0

# Abre o arquivo de configuracao e compila os padroes para melhor desempenho.
# Tem mais processamento na primeira rodagem por compilar todas as regras de uma vez.
with portalocker.Lock(caminho_de_configuracao, mode='rb', timeout=1) as arquivo_de_configuracao_puro:
    configuracao = yaml.safe_load(arquivo_de_configuracao_puro)

# O indice de leitura e estado local: pode nao existir na primeira execucao.
try:
    if os.path.exists(arquivo_de_estado):
        with open(arquivo_de_estado, 'r') as arquivo_json:
            relacao_pos_file = json.load(arquivo_json)
    else:
        relacao_pos_file = {}
except Exception as e:
    print(f"Arquivo de estado corrompido, reiniciando o indice do zero. Error={e}")
    relacao_pos_file = {}

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
            envia_sobrando()
    except KeyboardInterrupt:
        observer.stop()
    finally:
        print("Observador Morto")
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
        with portalocker.Lock(evento, mode="rb",timeout=1 ) as file:
            pos_inicial = relacao_pos_file[evento]
            file.seek(pos_inicial)
            conteudo = file.read()

            ultima_quebra = conteudo.rfind(b"\n")
            if ultima_quebra == -1 and pos_inicial != 0:
                # ainda nao ha nenhuma linha completa, espera o proximo evento
                return

            completo = conteudo[:ultima_quebra + 1]
            novas_linhas = completo.decode("utf-8",errors="replace").splitlines()

            # Reposiciona exatamente no fim da ultima linha completa.
            # seek() em modo texto so aceita posicoes vindas de tell(),
            # entao relemos so o trecho completo para obter uma posicao valida.
            with lock:
                relacao_pos_file[evento] = pos_inicial + len(completo)
            servico_do_evento = os.path.basename(os.path.dirname(evento))
            pre_filtro(novas_linhas, regras, servico_do_evento)

    except Exception:
        log_from_logging.exception("falha no pre_filtro, servico=%s", os.path.basename(os.path.dirname(evento)))

# Funções Auxiliares de escrita
def escreve_ponteiro(relacao_pos_file):
    # Grava num arquivo temporario no mesmo diretorio e troca com os.replace,
    # que e atomico: nunca deixa o arquivo de indice pela metade.
    with tempfile.NamedTemporaryFile('w', dir=diretorio_de_estado, delete=False) as f_temp:
        json.dump(relacao_pos_file,f_temp)
        f_temp.flush()
        os.fsync(f_temp.fileno())

    os.replace(f_temp.name, arquivo_de_estado)


def soma_mais_um(zera: bool):
    """ Soma sequencial de linhas lidas """
    global qtd
    if zera:
        qtd = 0
    else:
        qtd+=1

def update_batch(ultimas_linhas, servico_do_evento, regra):
    """ Adiciona as informações a batch de logs """
    global batch_de_logs
    batch_de_logs.update({qtd: [ultimas_linhas, servico_do_evento, regra]})

def clear_batch():
    """ Limpa a batch de logs a nivel global """
    global batch_de_logs
    batch_de_logs.clear()

def despacha_lote():
    """ Envia o que estiver acumulado e reinicia o contador e o relogio """
    global ultimo_envio
    ultimo_envio = time.monotonic()
    try:
        if qtd:
            if envio_para_API(batch_de_logs) == True:
                clear_batch()
                soma_mais_um(True)
                escreve_ponteiro(relacao_pos_file)

    except Exception as e:
        print(f"Depacha_lote, Error={e}")

def envia_sobrando():
    """ Despacha o lote incompleto quando o intervalo vence; chamado pelo observer """
    with lock:
        if qtd and time.monotonic() - ultimo_envio >= INTERVALO_DE_ENVIO:
            despacha_lote()

def finaliza_envio():
    """ Despacha o resto sem esperar o intervalo; usado no fim da carga inicial """
    with lock:
        despacha_lote()

def pre_filtro(ultimas_linhas, regras, servico_do_evento):
    """Classifica cada linha nova lida do log; o primeiro match (mais especifico) vence."""
    try:
        with lock:
            regras_do_servico = regras.get(servico_do_evento)
            if regras_do_servico is None:
                return

            if len(ultimas_linhas) >= 1:
                for cada_linha in ultimas_linhas:
                    linha = cada_linha.strip()
                    for regra in regras_do_servico:
                        if regra["padrao"].search(linha):
                            update_batch(linha, servico_do_evento, regra["id"])
                            soma_mais_um(False)
                            if qtd >= TAMANHO_DO_LOTE:
                                despacha_lote()
                            break

    except Exception:
        log_from_logging.exception("falha no pre_filtro, servico=%s", servico_do_evento)


def envio_para_API(batch_de_logs):
    """Envia o log classificado para o centralizador."""
    headers = {"Content-Type": "application/json"}
    data = {"batch": batch_de_logs}

    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        if response.status_code == 200:
            return True
        else:
            print(f"Falha ao enviar, Status code: {response.status_code}")

    except requests.exceptions.ConnectionError as error:
        print(f"API fora do ar, error={error}")

    except requests.exceptions.ConnectTimeout as error:
        print(f"API timeout, error={error}")

    except requests.exceptions.HTTPError as error:
        print(f"API HTTP, error={error}")

    #except requests.exceptions.RequestException:
    #    log_from_logging.exception("Erro ao enviar log para o centralizador")

if __name__ == "__main__":
    cria_observer()
