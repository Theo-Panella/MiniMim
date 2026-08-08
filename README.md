# MiniMim

Agente leve de coleta e pré-filtragem de logs. Monitora vários arquivos de log em tempo real e classifica cada linha nova com regras de regex por serviço.

A ideia é fazer a triagem **na ponta**: em vez de mandar o log inteiro pra um servidor central, o MiniMim decide localmente o que é relevante, reduzindo tráfego e processamento.

> Logs de amostra vêm do projeto [loghub](https://github.com/logpai/loghub.git).

---

## Estrutura

```
MiniMim-Agent/
├── minicli.py                 # CLI: carga inicial dos logs (--load)
├── minimim_refactor.py        # agente principal: watchdog + pré-filtro
├── ConfigurationFiles/
│   └── filter.yaml            # regras de filtragem, uma seção por serviço
├── Apache/, Openssh/          # pastas de log de amostra, uma por serviço
├── escreve_log_teste.py       # gera linhas de log continuamente, pra teste
└── .env                       # configuração local (não versionado)
```

O nome de cada pasta de log precisa bater com a seção correspondente no `filter.yaml` (ex: `Apache/` ↔ `Apache:`) — é assim que o agente escolhe as regras certas para cada arquivo.

> `MiniMim.py` é a versão original, de um único serviço/arquivo, mantida só de referência. `minimim_refactor.py` é a versão atual.

---

## Como funciona

1. Na inicialização, o `.env` é carregado e o `filter.yaml` é lido; as regras de cada serviço são compiladas e ordenadas por `especificidade` (maior primeiro).
2. O [watchdog](https://pypi.org/project/watchdog/) observa cada diretório listado em `LOG_PATH`. A cada modificação, o agente lê só as linhas novas de cada arquivo, guardando a posição do último `seek` por arquivo.
3. Cada linha nova é comparada com as regras do serviço deduzido do nome da pasta; o primeiro match — o mais específico — vence.

> **Status:** o envio para uma API central ainda não foi implementado; a classificação acontece mas não é enviada nem impressa.

---

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Configure o `.env`:

```dotenv
LOG_PATH = /caminho/para/Apache/,/caminho/para/Openssh/
CONFIGURATION_FILE = ConfigurationFiles/filter.yaml
```

`LOG_PATH` é uma lista de diretórios (um por serviço); `CONFIGURATION_FILE` aponta pro `filter.yaml`.

Carga inicial (lê o que já existe nos logs):

```bash
python minicli.py --load
```

Monitoramento contínuo:

```bash
python minimim_refactor.py
```

`escreve_log_teste.py` gera linhas de teste continuamente em `Openssh/OpenSSH_2k.log`, útil pra ver o watchdog reagir. Encerre qualquer processo com `Ctrl+C`.

---

## Roadmap

- [ ] Implementar o envio da linha classificada para uma API central
- [ ] Unificar `minicli.py` e `minimim_refactor.py` num único entrypoint
- [ ] Validar variáveis de ambiente na inicialização
- [ ] Tratar rotação/truncamento do arquivo de log
