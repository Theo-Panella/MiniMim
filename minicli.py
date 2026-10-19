#!/usr/bin/env python3
import argparse
import os
import re
import json
import random
import tempfile

import yaml
import time
import portalocker
import requests
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, MofNCompleteColumn, TextColumn, BarColumn, TimeRemainingColumn

load_dotenv()
CAMINHO_ENV = ".env"
CONFIGURACAO_PADRAO = os.path.join("Configuration_Files", "filter.yaml")

console = Console()

DESPEDIDAS = [
    "Bora caçar uns logs! 🕵️",
    "Os logs que lutem! 💪",
    "Café na mão, logs no radar. ☕",
    "Nenhum log fica pra trás! 🚀",
]


# --------------------------------------------------------------------------- #
# Utilitarios de saida
# --------------------------------------------------------------------------- #

def sucesso(texto):
    console.print(f"  [bold green]✔[/] {texto}")


def aviso(texto):
    console.print(f"  [bold yellow]⚠[/] [yellow]{texto}[/]")


def info(texto):
    console.print(f"  [cyan]•[/] {texto}")


def limpa_tela():
    """Limpa a tela e o historico de rolagem, pra so a execucao atual ficar visivel."""
    if not console.is_terminal:
        return
    if os.name == "nt":
        os.system("cls")
    else:
        # 2J limpa a tela, 3J apaga o historico de rolagem, H volta o cursor pro topo.
        console.file.write("\033[H\033[2J\033[3J")
        console.file.flush()


def linha():
    console.rule(style="magenta")


def titulo(texto):
    console.print()
    console.print(Panel.fit(f"[bold]{texto}[/]", border_style="magenta"))


# --------------------------------------------------------------------------- #
# Utilitarios de entrada
# --------------------------------------------------------------------------- #

def pergunta(texto, padrao=None):
    """Le uma resposta do usuario; Enter em branco devolve o padrao."""
    rotulo = f"[bold cyan]?[/] {escape(texto)}"
    if padrao:
        rotulo += f" [dim]{escape(f'[{padrao}]')}[/]"
    while True:
        resposta = console.input(rotulo + ": ").strip()
        if resposta:
            return resposta
        if padrao is not None:
            return padrao
        aviso("Opa, essa aqui é obrigatória! 😅")


def confirma(texto, padrao=True):
    """Pergunta sim/nao. Enter em branco devolve o padrao."""
    sufixo = "[S/n]" if padrao else "[s/N]"
    while True:
        resposta = console.input(f"[bold cyan]?[/] {escape(texto)} [dim]{escape(sufixo)}[/]: ").strip().lower()
        if not resposta:
            return padrao
        if resposta in ("s", "sim", "y", "yes"):
            return True
        if resposta in ("n", "nao", "não", "no"):
            return False
        aviso("É só um s ou n, prometo que não dói! 😉")


def pergunta_inteiro(texto, padrao):
    while True:
        resposta = pergunta(texto, str(padrao))
        try:
            return int(resposta)
        except ValueError:
            aviso("Hmm, isso não parece um número inteiro 🤔")


# --------------------------------------------------------------------------- #
# Leitura/escrita do filter.yaml
# --------------------------------------------------------------------------- #

def carrega_configuracao(caminho):
    """Devolve (regras, cabecalho de comentarios) do filter.yaml."""
    if not os.path.exists(caminho):
        return {}, ""

    with open(caminho, 'r', encoding='utf-8') as arquivo_de_configuracao:
        linhas = arquivo_de_configuracao.readlines()

    cabecalho = []
    for linha in linhas:
        if linha.startswith('#') or not linha.strip():
            cabecalho.append(linha)
        else:
            break

    conteudo = yaml.safe_load(''.join(linhas)) or {}
    return conteudo, ''.join(cabecalho)


def salva_configuracao(caminho, regras, cabecalho=""):
    """Reescreve o filter.yaml preservando o bloco de comentarios do topo."""
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    with open(caminho, 'w', encoding='utf-8') as arquivo_de_configuracao:
        if cabecalho.strip():
            arquivo_de_configuracao.write(cabecalho.rstrip('\n') + '\n\n')
        yaml.safe_dump(regras, arquivo_de_configuracao, allow_unicode=True,
                       sort_keys=False, default_flow_style=False)



# --------------------------------------------------------------------------- #
# Tutorial
# --------------------------------------------------------------------------- #

def coleta_regras(servico, regras_existentes):
    """Coleta interativamente as regras de um servico e devolve o dict do servico."""
    regras = dict(regras_existentes or {})

    if regras:
        console.print()
        info(f"O serviço [bold]{escape(servico)}[/] já tem {len(regras)} regra(s): {escape(', '.join(regras))}")
        if not confirma("Quer adicionar mais regras?", padrao=False):
            return regras

    console.print()
    info("Cada regra tem um nome único, um padrão regex e uma especificidade.")
    info("A especificidade define a ordem: quanto maior, mais cedo a regra é testada. 🏁")

    while True:
        id_padrao = pergunta("Nome da regra (Enter para encerrar o serviço)", padrao="")
        if not id_padrao:
            break

        if id_padrao in regras and not confirma(f"'{id_padrao}' já existe. Sobrescrever?", padrao=False):
            continue

        while True:
            padrao = pergunta("Padrão regex")
            try:
                re.compile(padrao)
                break
            except re.error as erro:
                aviso(f"Essa regex tropeçou: {escape(str(erro))} 🙃")

        especificidade = pergunta_inteiro("Especificidade", padrao=1)

        regras[id_padrao] = {
            "padrao": padrao,
            "especificidade": especificidade,
        }
        sucesso(f"Regra [bold]{escape(id_padrao)}[/] registrada! 🎯")

    if not regras:
        aviso(f"Nenhuma regra para '{escape(servico)}': o agente vai ignorar esse diretório. 🙈")

    return regras

def executa_tutorial():
    """Passo a passo interativo que monta o .env e o filter.yaml."""
    console.print(Panel.fit(
        "[bold magenta]Oi! Eu sou o MiniMim 👋[/]\n\n"
        "Vamos montar juntos o [bold].env[/] e o [bold]filter.yaml[/] em 4 passinhos.\n"
        "[dim]Enter aceita o valor entre colchetes. Ctrl+C cancela sem gravar nada.[/]",
        title="✨ Configuração inicial ✨", border_style="magenta"))

    # ---- 1. arquivo de regras ---------------------------------------------
    titulo("📜 1/4 - Arquivo de regras")
    atual = os.getenv('CONFIGURATION_FILE') or CONFIGURACAO_PADRAO
    caminho_de_configuracao = os.path.abspath(
        os.path.expanduser(pergunta("Caminho do filter.yaml", padrao=atual)))

    configuracao, cabecalho = carrega_configuracao(caminho_de_configuracao)
    if configuracao:
        sucesso(f"Achei! O arquivo tem {len(configuracao)} serviço(s): {escape(', '.join(configuracao))}")
    else:
        info("Arquivo novinho em folha 🌱 - ele nasce no final do tutorial.")

    # ---- 2. diretorios de log ---------------------------------------------
    titulo("📂 2/4 - Diretórios de log")
    info("Cada diretório corresponde a um serviço. O nome da pasta escolhe a")
    info("seção de regras usada na filtragem (ex: Apache/ -> Apache:).")

    ja_configurados = [p for p in (os.getenv('LOG_PATH') or '').split(',') if p.strip()]
    diretorios = []
    if ja_configurados:
        console.print()
        info(f"Já configurados: {escape(', '.join(ja_configurados))}")
        if confirma("Quer manter esses diretórios?", padrao=True):
            diretorios = list(ja_configurados)

    while True:
        console.print()
        entrada = pergunta("Diretório de log (Enter para encerrar)", padrao="")
        if not entrada:
            if diretorios:
                break
            aviso("Preciso de pelo menos um diretório pra vigiar! 👀")
            continue

        diretorio = entrada

        if not os.path.isdir(diretorio):
            if confirma(f"'{diretorio}' não existe. Crio pra você?", padrao=True):
                os.makedirs(diretorio, exist_ok=True)
                sucesso("Diretório criado! 🏗️")
            else:
                info("Beleza, vou fingir que não vi esse. 🙈")
                continue

        if diretorio in diretorios:
            info("Esse aí já estava na lista. 😉")
        else:
            diretorios.append(diretorio)
            sucesso(escape(diretorio))

        servico_padrao = os.path.basename(os.path.normpath(diretorio))
        servico = pergunta("Nome do serviço", padrao=servico_padrao)
        configuracao[servico] = coleta_regras(servico, configuracao.get(servico))

    # ---- 3. endereço da API ---------------------------------------------
    titulo("🌐 3/4 - Endereço da API")
    endereco_api = pergunta("Endereço da API - http://[Endereço]:8000", padrao="127.0.0.1")


    # ---- 4. resumo e gravacao ---------------------------------------------
    titulo("📋 4/4 - Resumo")
    console.print(f"[bold]Arquivo de regras[/] : {escape(caminho_de_configuracao)}")
    console.print("[bold]Diretórios[/]        :")
    for diretorio in diretorios:
        console.print(f"  📁 {escape(diretorio)}")
    console.print("[bold]Serviços[/]          :")
    for servico, padroes in configuracao.items():
        console.print(f"  🧩 {escape(servico)}: {len(padroes or {})} regra(s)")

    console.print()
    if not confirma("Posso gravar essa configuração?", padrao=True):
        info("Tranquilo, nada foi gravado. Volte quando quiser! 👋")
        return

    salva_configuracao(caminho_de_configuracao, configuracao, cabecalho)
    sucesso(f"{escape(caminho_de_configuracao)} atualizado.")

    if not os.path.exists(CAMINHO_ENV):
        open(CAMINHO_ENV, 'w', encoding='utf-8').close()
    set_key(CAMINHO_ENV, "LOG_PATH", ",".join(diretorios))
    set_key(CAMINHO_ENV, "CONFIGURATION_FILE", caminho_de_configuracao)

    caminho_json_state = "Configuration_Files/filestate.json"
    caminho_json_API = "Configuration_Files/API_SS.json"
    diretorio_json = os.path.dirname(caminho_json_state) or "."

    if not os.path.exists(caminho_json_state):

        os.makedirs(diretorio_json, exist_ok=True)
        with open(caminho_json_state, 'w', encoding='utf-8') as arquivo_json:
            json.dump({}, arquivo_json)
        sucesso(f"{escape(caminho_json_state)} criado.")

    # Nao sobrescreve: o arquivo pode ter lotes pendentes de reenvio.
    if not os.path.exists(caminho_json_API):
        with open(caminho_json_API, 'w', encoding='utf-8') as arquivo_estado_api:
            json.dump([], arquivo_estado_api)

    set_key(CAMINHO_ENV, "STATE_DIR", diretorio_json)
    set_key(CAMINHO_ENV, "STATE_FILE", caminho_json_state)
    set_key(CAMINHO_ENV, "API_URL", f"http://{endereco_api}:8000")
    set_key(CAMINHO_ENV, "API_FILE_PATH", f"{diretorio_json}/")
    set_key(CAMINHO_ENV, "API_SS_FILE", f"API_SS.json")
    sucesso(f"{escape(os.path.abspath(CAMINHO_ENV))} atualizado.")

    console.print()
    console.print(Panel.fit(
        "[bold green]Tudo pronto! 🎉[/]\n\n"
        "Próximos passos:\n"
        "  [cyan]minicli --load[/]     [dim]# carga inicial dos logs existentes[/]\n"
        "  [cyan]minicli --observe[/]  [dim]# monitoramento contínuo[/]\n\n"
        f"[italic magenta]{random.choice(DESPEDIDAS)}[/]",
        border_style="green"))


# --------------------------------------------------------------------------- #
# Reenvio dos lotes salvos
# --------------------------------------------------------------------------- #

def grava_lotes_pendentes(apifile_path, caminho_completo, lotes_pendentes):
    """Regrava o arquivo de lotes pendentes de forma atomica."""
    with tempfile.NamedTemporaryFile(mode="w", dir=apifile_path, delete=False) as f_temp:
        json.dump(lotes_pendentes, f_temp)
        f_temp.flush()
        os.fsync(f_temp.fileno())
    os.replace(f_temp.name, caminho_completo)


def envia_lotes_pendentes(apifile_path, api_SS):
    """Reenvia para a API os lotes salvos em disco, tirando cada um do arquivo assim que despachado."""
    caminho_completo = apifile_path + api_SS
    url = os.getenv('API_URL')

    if not url:
        aviso("Não sei onde fica a API 🗺️  Rode: [bold]minicli --tutorial[/]")
        return

    if not os.path.exists(caminho_completo):
        sucesso("Nenhum lote pendente. Tudo em dia! 😎")
        return

    try:
        with portalocker.Lock(caminho_completo, mode='rb', timeout=1) as apifile_SS:
            lotes_pendentes = json.load(apifile_SS)
    except json.JSONDecodeError as erro:
        aviso(f"O arquivo de lotes está bagunçado: {escape(str(erro))} 😵")
        return

    if not isinstance(lotes_pendentes, list):
        aviso("Arquivo de lotes em formato antigo/inválido, nada pra enviar. 🤷")
        return

    if not lotes_pendentes:
        sucesso("Nenhum lote pra enviar. Tudo em dia! 😎")
        return

    headers = {"Content-Type": "application/json"}
    enviados = 0

    # Itera sobre uma copia: cada lote enviado com sucesso sai de lotes_pendentes
    # e o arquivo e regravado na hora, entao uma interrupcao no meio do laco
    # nao reenvia de novo o que ja foi despachado.
    for lote in list(lotes_pendentes):
        try:
            response = requests.post(url, json={"batch": lote}, headers=headers, timeout=5)
        except requests.exceptions.ConnectionError as erro:
            aviso(f"A API está tirando um cochilo 😴 error={escape(str(erro))}")
            # Sem conexao com a API agora, os lotes seguintes tambem vao falhar.
            break
        except requests.exceptions.RequestException as erro:
            aviso(f"Deu ruim no envio 😬 error={escape(str(erro))}")
            continue

        if response.status_code != 200:
            aviso(f"A API respondeu torto, status code: {response.status_code} 🫤")
            continue

        enviados += 1
        lotes_pendentes.remove(lote)
        grava_lotes_pendentes(apifile_path, caminho_completo, lotes_pendentes)

    linha()
    if lotes_pendentes:
        console.print(f"📦 [bold green]{enviados}[/] lote(s) enviado(s), "
                      f"[bold yellow]{len(lotes_pendentes)}[/] ainda pendente(s). Tento de novo depois! 💪")
    else:
        console.print(f"🚀 [bold green]{enviados}[/] lote(s) enviado(s), nada pendente. Missão cumprida! 🎉")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

class AjudaEmPortugues(argparse.HelpFormatter):
    """Troca o prefixo 'usage:' do argparse por 'uso:'."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "uso: ")


def main():
    parser = argparse.ArgumentParser(prog='MiniMim',
                                     description='🐭 O melhor agente de coleta do bairro! Caço seus logs e mando tudo pra API.',
                                     epilog='Primeira vez por aqui? Comece com: minicli --tutorial ✨',
                                     formatter_class=AjudaEmPortugues,
                                     add_help=False)
    # Titulo da secao de argumentos, que o argparse escreve em ingles por padrao.
    parser._optionals.title = "opcoes"

    parser.add_argument('-h','--help', action='help', help="Mostra esta mensagem de ajuda e sai")
    parser.add_argument('-t','--tutorial', action='store_true', help="Configuracao interativa passo a passo dos arquivos de configuracao")
    parser.add_argument('-l','--load', action='store_true', help="Faz a carga inicial dos arquivos nos diretorios definidos no .env")
    parser.add_argument('-o','--observe', action='store_true', help="Inicia a observacao continua dos diretorios de log")
    parser.add_argument('-c','--clean', action='store_true', help="Limpa o arquivo do ponteiro de leitura")
    parser.add_argument('-sta','--sendtoapi', action='store_true', help="Envia batchs salvas para API")

    limpa_tela()
    args = parser.parse_args()

    log_path = [p for p in (os.getenv('LOG_PATH') or '').split(',') if p.strip()]

    arquivo_de_estado = os.getenv('STATE_FILE')

    caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')

    if args.tutorial:
        try:
            executa_tutorial()
        except (KeyboardInterrupt, EOFError):
            console.print()
            info("Tutorial cancelado. Nada foi gravado, até a próxima! 👋")
        return

    if args.load:
        start = time.perf_counter()
        if not log_path or not arquivo_de_estado or not caminho_de_configuracao:
            aviso("Ainda não estou configurado 🙈 Rode: [bold]minicli --tutorial[/]")
            return
        console.print("[bold magenta]🕵️  Iniciando a caça aos logs![/]")
        linha()

        # Import tardio: MiniMim le o .env no import e exige config valida.
        from MiniMim import popula_indice, finaliza_envio
        for workdir in log_path:
            with Progress(TextColumn(f"[progress.description]📂 Vasculhando {escape(workdir)}..."),
                          BarColumn(complete_style="magenta"), MofNCompleteColumn(), TimeRemainingColumn(),
                          console=console) as progress:
                task = progress.add_task(f"[green]", total=sum(1 for arquivo_teste in os.scandir(workdir) if arquivo_teste.is_file()))
                for arquivo in os.scandir(workdir):
                    popula_indice(os.path.join(workdir, arquivo.name))
                    progress.update(task, advance=1)
            sucesso(f"Diretório [bold]{escape(workdir)}[/] finalizado!")
            linha()

        # O processo termina logo abaixo: manda o que sobrou do ultimo lote.
        finaliza_envio()

        end = time.perf_counter()
        total = end - start
        console.print(f"🎉 [bold green]Coleta inicial finalizada[/] em [bold]{total:.2f}s[/]!")
        linha()
        console.print("Agora deixa comigo: rode [cyan]minicli -o[/] ou [cyan]minicli --observe[/] pra eu ficar de olho 👀")

        return

    if args.observe:
        if not log_path or not arquivo_de_estado or not caminho_de_configuracao:
            aviso("Ainda não estou configurado 🙈 Rode: [bold]minicli --tutorial[/]")
            return
        else:
            from MiniMim import cria_observer
            console.print("[bold magenta]👀 De olho nos seus logs![/] [dim](Ctrl+C pra me dar folga)[/]")
            cria_observer()
            return

    if args.clean:
        if arquivo_de_estado:
            json_aberto = open(arquivo_de_estado,"w")
            json.dump({},json_aberto)
            json_aberto.close()
            console.print(Panel.fit("🧹 [bold green]Ponteiro de leitura zerado![/] Brilhando de limpo ✨", border_style="green"))
            return
        else:
            aviso("Não achei o arquivo .json 🔍 Já rodou o [bold]minicli --tutorial[/]?")
            return

    if args.sendtoapi:
        apifile_path = os.getenv('API_FILE_PATH', 'Configuration_Files/')
        api_SS = os.getenv('API_SS_FILE', 'API_SS.json') # API Save State.json
        envia_lotes_pendentes(apifile_path, api_SS)
        return

    else:
        parser.print_help()

if __name__ == "__main__":
    load_dotenv()
    main()
