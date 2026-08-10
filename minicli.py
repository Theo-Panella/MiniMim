#!/usr/bin/env python3
import argparse
from minimim_refactor import popula_indice
import os
import yaml
from dotenv import load_dotenv, set_key

def main(log_path):
    parser = argparse.ArgumentParser(prog='MiniMim',description='The best CLI agent in my neighborhood')

    parser.add_argument('--workdir', type=str, help="Specify a new path to monitore (it adds to the .env file and configure the inicial yaml filter)")
    parser.add_argument('-start', action='store_true', help="Start MiniMim using the pre done configuration")

    args = parser.parse_args()

    #try:
    if args.workdir:
        print("Atribuindo caminho para .env")
        log_path.append(args.workdir)
        junta = ",".join(log_path)
        set_key(".env","LOG_PATH",junta)


        print("criando configuracao inicial para filter.yaml")

        servico = input(str("Serviço do caminho: "))
        id_padrao = "Nome unico do padrao de busca"
        padrao = "Padrao de procura"
        especificidade = 1

        regras = {
            servico: {
                id_padrao: {
                    "padrao": padrao, 
                    "especificidade": especificidade
                }
            }
        }

        with open(caminho_de_configuracao, 'a', encoding='utf-8') as arquivo_de_configuracao:
            arquivo_de_configuracao.write('\n')
            yaml.safe_dump(regras, arquivo_de_configuracao, allow_unicode=True, sort_keys=False)
   

    elif args.start:
        for workdir in log_path:
            for arquivo in os.scandir(workdir):
                popula_indice(workdir+arquivo.name)
    else:
        print("Diretorio não informado")
    
    #except:
    #    print("error")

if __name__ == "__main__":
    load_dotenv()
    log_path = os.getenv('LOG_PATH').split(',')
    caminho_de_configuracao = os.getenv('CONFIGURATION_FILE')
    main(log_path)