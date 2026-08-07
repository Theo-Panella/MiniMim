#!/usr/bin/env python3
import argparse
from minimim_refactor import popula_indice
import os
from dotenv import load_dotenv

def main(log_path):
    parser = argparse.ArgumentParser(prog='MiniMim',description='The best CLI agent in Limeira/SP')

    parser.add_argument('-l', '--load', action='store_true' , help="Do the first load using the .env config")

    args = parser.parse_args()

    try:
        if args.load:
            for workdir in log_path:
                for arquivo in os.scandir(workdir):
                    popula_indice(workdir+arquivo.name)
        else:
            print("Diretorio não informado")
    
    except:
        print("error")

if __name__ == "__main__":
    load_dotenv()
    log_path = os.getenv('LOG_PATH').split(',')
    main(log_path)