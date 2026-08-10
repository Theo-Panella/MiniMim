#!/usr/bin/env python3
import argparse
import os
import re

import yaml
from dotenv import load_dotenv, set_key

CAMINHO_ENV = ".env"
CONFIGURACAO_PADRAO = os.path.join("ConfigurationFiles", "filter.yaml")


# --------------------------------------------------------------------------- #
# Utilitarios de entrada
# --------------------------------------------------------------------------- #

def pergunta(texto, padrao=None):
    """Le uma resposta do usuario; Enter em branco devolve o padrao."""
    rotulo = f"{texto} [{padrao}]: " if padrao else f"{texto}: "
    while True:
        resposta = input(rotulo).strip()
        if resposta:
            return resposta
        if padrao is not None:
            return padrao
        print("  ! Resposta obrigatoria.")


def confirma(texto, padrao=True):
    """Pergunta sim/nao. Enter em branco devolve o padrao."""
    sufixo = "[S/n]" if padrao else "[s/N]"
    while True:
        resposta = input(f"{texto} {sufixo}: ").strip().lower()
        if not resposta:
            return padrao
        if resposta in ("s", "sim", "y", "yes"):
            return True
        if resposta in ("n", "nao", "não", "no"):
            return False
        print("  ! Responda com s ou n.")


def pergunta_inteiro(texto, padrao):
    while True:
        resposta = pergunta(texto, str(padrao))
        try:
            return int(resposta)
        except ValueError:
            print("  ! Informe um numero inteiro.")


def titulo(texto):
    print()
    print("=" * 60)
    print(texto)
    print("=" * 60)


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


def normaliza_diretorio(caminho):
    """Caminho absoluto terminando em separador: o agente concatena o nome do arquivo."""
    absoluto = os.path.abspath(os.path.expanduser(caminho))
    return absoluto + os.sep


# --------------------------------------------------------------------------- #
# Tutorial
# --------------------------------------------------------------------------- #

def coleta_regras(servico, regras_existentes):
    """Coleta interativamente as regras de um servico e devolve o dict do servico."""
    regras = dict(regras_existentes or {})

    if regras:
        print(f"\n  O servico '{servico}' ja tem {len(regras)} regra(s): {', '.join(regras)}")
        if not confirma("  Quer adicionar mais regras?", padrao=False):
            return regras

    print("\n  Cada regra tem um nome unico, um padrao regex e uma especificidade.")
    print("  A especificidade define a ordem: quanto maior, mais cedo a regra e testada.")

    while True:
        id_padrao = pergunta("  Nome da regra (Enter para encerrar o servico)", padrao="")
        if not id_padrao:
            break

        if id_padrao in regras and not confirma(f"  '{id_padrao}' ja existe. Sobrescrever?", padrao=False):
            continue

        while True:
            padrao = pergunta("  Padrao regex")
            try:
                re.compile(padrao)
                break
            except re.error as erro:
                print(f"  ! Regex invalida: {erro}")

        especificidade = pergunta_inteiro("  Especificidade", padrao=1)

        regras[id_padrao] = {
            "padrao": padrao,
            "especificidade": especificidade,
        }
        print(f"  + Regra '{id_padrao}' registrada.")

    if not regras:
        print(f"  ! Nenhuma regra para '{servico}': o agente vai ignorar esse diretorio.")

    return regras


def executa_tutorial():
    """Passo a passo interativo que monta o .env e o filter.yaml."""
    titulo("MiniMim - Configuracao inicial")
    print("Este tutorial monta o .env e o filter.yaml respondendo algumas perguntas.")
    print("Enter aceita o valor entre colchetes. Ctrl+C cancela sem gravar nada.")

    # ---- 1. arquivo de regras ---------------------------------------------
    titulo("1/3 - Arquivo de regras")
    atual = os.getenv('CONFIGURATION_FILE') or CONFIGURACAO_PADRAO
    caminho_de_configuracao = os.path.abspath(
        os.path.expanduser(pergunta("Caminho do filter.yaml", padrao=atual)))

    configuracao, cabecalho = carrega_configuracao(caminho_de_configuracao)
    if configuracao:
        print(f"  Arquivo encontrado com {len(configuracao)} servico(s): {', '.join(configuracao)}")
    else:
        print("  Arquivo novo - sera criado ao final do tutorial.")

    # ---- 2. diretorios de log ---------------------------------------------
    titulo("2/3 - Diretorios de log")
    print("Cada diretorio corresponde a um servico. O nome da pasta escolhe a")
    print("secao de regras usada na filtragem (ex: Apache/ -> Apache:).")

    ja_configurados = [p for p in (os.getenv('LOG_PATH') or '').split(',') if p.strip()]
    diretorios = []
    if ja_configurados:
        print(f"\n  Ja configurados: {', '.join(ja_configurados)}")
        if confirma("  Quer manter esses diretorios?", padrao=True):
            diretorios = list(ja_configurados)

    while True:
        entrada = pergunta("\n  Diretorio de log (Enter para encerrar)", padrao="")
        if not entrada:
            if diretorios:
                break
            print("  ! Informe pelo menos um diretorio.")
            continue

        diretorio = normaliza_diretorio(entrada)

        if not os.path.isdir(diretorio):
            if confirma(f"  '{diretorio}' nao existe. Criar?", padrao=True):
                os.makedirs(diretorio, exist_ok=True)
            else:
                print("  - Diretorio ignorado.")
                continue

        if diretorio in diretorios:
            print("  - Diretorio ja estava na lista.")
        else:
            diretorios.append(diretorio)
            print(f"  + {diretorio}")

        servico_padrao = os.path.basename(os.path.normpath(diretorio))
        servico = pergunta("  Nome do servico", padrao=servico_padrao)
        configuracao[servico] = coleta_regras(servico, configuracao.get(servico))

    # ---- 3. resumo e gravacao ---------------------------------------------
    titulo("3/3 - Resumo")
    print(f"Arquivo de regras : {caminho_de_configuracao}")
    print("Diretorios        :")
    for diretorio in diretorios:
        print(f"  - {diretorio}")
    print("Servicos          :")
    for servico, padroes in configuracao.items():
        print(f"  - {servico}: {len(padroes or {})} regra(s)")

    if not confirma("\nGravar essa configuracao?", padrao=True):
        print("Nada foi gravado.")
        return

    salva_configuracao(caminho_de_configuracao, configuracao, cabecalho)
    print(f"  + {caminho_de_configuracao} atualizado.")

    if not os.path.exists(CAMINHO_ENV):
        open(CAMINHO_ENV, 'w', encoding='utf-8').close()
    set_key(CAMINHO_ENV, "LOG_PATH", ",".join(diretorios))
    set_key(CAMINHO_ENV, "CONFIGURATION_FILE", caminho_de_configuracao)
    print(f"  + {os.path.abspath(CAMINHO_ENV)} atualizado.")

    print("\nPronto. Proximos passos:")
    print("  python minicli.py -start     # carga inicial dos logs existentes")
    print("  python minimim_refactor.py   # monitoramento continuo")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(prog='MiniMim', description='The best CLI agent in my neighborhood')

    parser.add_argument('-t','--tutorial', action='store_true', help="Interactive step-by-step setup of the .env and filter.yaml files")
    parser.add_argument('--start', action='store_true', help="Start MiniMim using the pre done configuration")

    args = parser.parse_args()

    if args.tutorial:
        try:
            executa_tutorial()
        except (KeyboardInterrupt, EOFError):
            print("\nTutorial cancelado.")
        return

    log_path = [p for p in (os.getenv('LOG_PATH') or '').split(',') if p.strip()]
    caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')

    if args.start:
        if not log_path:
            print("LOG_PATH nao configurado. Rode: python minicli.py --tutorial")
            return
        # Import tardio: minimim_refactor le o .env no import e exige config valida.
        from minimim_refactor import popula_indice
        for workdir in log_path:
            for arquivo in os.scandir(workdir):
                popula_indice(os.path.join(workdir, arquivo.name))
    else:
        parser.print_help()


if __name__ == "__main__":
    load_dotenv()
    main()
