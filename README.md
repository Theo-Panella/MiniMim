# MiniMim

Agente leve de coleta e pré-filtragem de logs. Monitora vários arquivos de log em tempo real e classifica cada linha nova com regras de regex por serviço.

A ideia é fazer a triagem **na ponta**: em vez de mandar o log inteiro pra um servidor central, o MiniMim decide localmente o que é relevante, reduzindo tráfego e processamento.

> Logs de amostra vêm do projeto [loghub](https://github.com/logpai/loghub.git).

---

## Estrutura

```
MiniMim-Agent/
├── minicli.py                 # CLI: tutorial, carga inicial e observação
├── minimim_refactor.py        # agente principal: watchdog + pré-filtro
├── ConfigurationFiles/
│   ├── filter.yaml            # regras de filtragem, uma seção por serviço
│   └── relacao_pos_file.json  # índice de leitura por arquivo (não versionado)
├── Apache/, Openssh/          # pastas de log de amostra, uma por serviço
├── escreve_log_teste.py       # gera linhas de log continuamente, pra teste
└── .env                       # configuração local (não versionado)
```

O nome de cada pasta de log precisa bater com a seção correspondente no `filter.yaml` (ex: `Apache/` ↔ `Apache:`) — é assim que o agente escolhe as regras certas para cada arquivo.

> `MiniMim.py` é a versão original, de um único serviço/arquivo, mantida só de referência. `minimim_refactor.py` é a versão atual.

---

## Como funciona

1. Na inicialização, o `.env` é carregado, o `filter.yaml` é lido e o índice de posições em `JSON_PATH` é restaurado; as regras de cada serviço são compiladas e ordenadas por `especificidade` (maior primeiro).
2. O [watchdog](https://pypi.org/project/watchdog/) observa cada diretório listado em `LOG_PATH`. A cada modificação, o agente lê só as linhas novas de cada arquivo e regrava a posição do último `seek` no arquivo de índice, então a leitura continua de onde parou entre execuções.
3. Cada linha nova é comparada com as regras do serviço deduzido do nome da pasta; o primeiro match — o mais específico — vence.

> **Status:** `envio_para_API()` já faz o POST da linha classificada, mas a chamada está comentada no `pre_filtro` — hoje a classificação acontece sem ser enviada.

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
JSON_PATH = ConfigurationFiles/relacao_pos_file.json
```

`LOG_PATH` é uma lista de diretórios (um por serviço); `CONFIGURATION_FILE` aponta pro `filter.yaml`; `JSON_PATH` é onde o índice de leitura é gravado.

O tutorial interativo monta o `.env` e o `filter.yaml` respondendo perguntas:

```bash
python minicli.py -t
```

Carga inicial (lê o que já existe nos logs):

```bash
python minicli.py -s
```

Monitoramento contínuo:

```bash
python minicli.py -b
```

`escreve_log_teste.py` gera linhas de teste continuamente em `Openssh/OpenSSH_2k.log`, útil pra ver o watchdog reagir. Encerre qualquer processo com `Ctrl+C`.

---

## Roadmap

- [x] Envio da linha classificada para uma API central — falta reativar a chamada no `pre_filtro`
- [x] Unificar as duas entradas num único CLI (`minicli.py`)
- [ ] Concluir a flag `-clean`, que hoje só pede confirmação
- [ ] Validar variáveis de ambiente na inicialização
- [ ] Tratar rotação/truncamento do arquivo de log
