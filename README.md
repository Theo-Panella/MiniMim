# MiniMim

<p align="center">
  <img src="logo.png" alt="MiniMim" width="300">
</p>

Agente leve de coleta e pré-filtragem de logs. Monitora vários arquivos de log em tempo real e classifica cada linha nova com regras de regex por serviço.

A ideia é fazer a triagem **na ponta**: em vez de mandar o log inteiro pra um servidor central, o MiniMim decide localmente o que é relevante, reduzindo tráfego e processamento.

> Logs de amostra vêm do projeto [loghub](https://github.com/logpai/loghub.git).

---

## Estrutura

```
MiniMim-Agent/
├── minicli.py                 # CLI: tutorial, carga inicial e observação
├── MiniMim.py                 # agente principal: watchdog + pré-filtro
├── api.py                     # centralizador de logs (Flask), recebe os POSTs do agente
├── Configuration_Files/
│   ├── filter.yaml            # regras de filtragem, uma seção por serviço
│   └── filestate.json         # índice de leitura por arquivo, versionado vazio
├── Log_paths/
│   ├── Apache/                # pastas de log de amostra, uma por serviço
│   └── Openssh/
├── escreve_log_teste.py       # gera linhas de log continuamente, pra teste
└── .env                       # configuração local (não versionado)
```

O nome de cada pasta de log precisa bater com a seção correspondente no `filter.yaml` (ex: `Apache/` ↔ `Apache:`) — é assim que o agente escolhe as regras certas para cada arquivo.

---

## Como funciona

1. Na inicialização, o `.env` é carregado, o `filter.yaml` é lido e o índice de posições em `STATE_FILE` é restaurado; as regras de cada serviço são compiladas e ordenadas por `especificidade` (maior primeiro).
2. O [watchdog](https://pypi.org/project/watchdog/) observa cada diretório listado em `LOG_PATH`. A cada modificação, o agente lê só as linhas novas de cada arquivo e regrava a posição do último `seek` no arquivo de índice, então a leitura continua de onde parou entre execuções.
3. Cada linha nova é comparada com as regras do serviço deduzido do nome da pasta; o primeiro match — o mais específico — vence.
4. Cada linha que casa vai para `envio_para_API()`, num POST para o endpoint definido em .env.
> `api.py` é somente para teste de funcionalidade por enquanto, não possui autenticação e roda em debug de forma proposital

---

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Configure o `.env`:

```dotenv
LOG_PATH = /caminho/para/Apache/,/caminho/para/Openssh/
CONFIGURATION_FILE = Configuration_Files/filter.yaml
STATE_DIR = Configuration_Files/
STATE_FILE = Configuration_Files/filestate.json
API_URL = http://127.0.0.1:8000
API_FILE_PATH = Configuration_Files/
API_SS_FILE = API_SS.json
```

`LOG_PATH` é uma lista de diretórios (um por serviço); `CONFIGURATION_FILE` aponta pro `filter.yaml`; `STATE_FILE` é o arquivo onde o índice de leitura é gravado, e `STATE_DIR` é o diretório que o contém (usado pra gravar o índice de forma atômica: escreve num arquivo temporário nesse diretório e troca pelo `STATE_FILE` só no final). `API_URL` é o endereço do centralizador (`api.py`). `API_FILE_PATH`/`API_SS_FILE` apontam pro arquivo onde ficam os lotes que falharam o envio, pendentes de reenvio. O tutorial grava todas.

O tutorial interativo monta o `.env` e o `filter.yaml` respondendo perguntas:

```bash
python minicli.py -t
```

Carga inicial (lê o que já existe nos logs):

```bash
python minicli.py -l
```

Monitoramento contínuo:

```bash
python minicli.py -o
```

Limpa o ponteiro de leitura:

```bash
python minicli.py -c
```

Reenvia pra API os lotes que falharam o envio e ficaram salvos localmente (em `API_FILE_PATH`/`API_SS_FILE`):

```bash
python minicli.py -sta
```

`Log_paths/` não é versionado (`*.log` está no `.gitignore`), então num clone novo não há logs de amostra. `escreve_log_teste.py` cria `Log_paths/Openssh/OpenSSH_2k.log` e gera linhas de teste continuamente nele, útil pra ver o watchdog reagir (rode da raiz do projeto). Encerre qualquer processo com `Ctrl+C`.

A API que recebe os logs precisa estar de pé antes da coleta. O `gunicorn` só roda em Linux — ele importa `fcntl` —, então no Windows use o `waitress`:

```bash
waitress-serve --host=127.0.0.1 --port=8000 api:app   # Windows
gunicorn --bind 127.0.0.1:8000 api:app                # Linux
```

---

## Docker

```bash
docker compose up -d --build
```

Sobe `api` (porta `8000` exposta no host) e `agent`, que fica de pé com `sleep infinity` sem coletar nada sozinho: a coleta é disparada com `docker compose exec` (abaixo). O `agent` só fica na rede `iso`, interna — ele fala com a `api` pelo nome do serviço (`http://api:8000`), não por `127.0.0.1`. O `Log_paths/` do host **não** é um bind mount: no Docker Desktop o `inotify` não recebe eventos de escritas feitas no host através dele, e o `minicli -o` nunca reagiria. Em vez disso o `compose.yml` usa o Compose Watch (`develop.watch`, ação `sync`), que copia os logs alterados do host para `/app/Log_paths` dentro do container. Sem o `watch` rodando nada é sincronizado: o container só tem a cópia que entrou na imagem no build, e num clone novo ela é vazia.

O `.env` **não** é gerado dentro do container e o `compose.yml` falha se ele não existir no host. Rode o tutorial no host antes de subir (`python minicli.py -t`); o `env_file: .env` do `compose.yml` injeta as variáveis no `agent` na subida. Como o tutorial grava caminhos do host, ajuste manualmente no `.env` os que precisam apontar pro filesystem do container (prefixo `/app/`), por exemplo:

```dotenv
LOG_PATH = /app/Log_paths/Apache,/app/Log_paths/Openssh
CONFIGURATION_FILE = /app/Configuration_Files/filter.yaml
API_URL = http://api:8000
API_FILE_PATH = /app/Configuration_Files/
```

Como `Log_paths/` não é versionado, crie as pastas (`Log_paths/Apache`, `Log_paths/Openssh`) com alguns logs antes de subir.

Em um terminal, deixe o `watch` rodando (ele fica em primeiro plano e recria o `agent` ao iniciar):

```bash
docker compose watch
```

Espere a mensagem `Watch enabled` e, em outro terminal, dispare a coleta e os demais comandos com `exec`. Não use `exec` antes disso: o `agent` é recriado e o comando morre junto.

```bash
docker compose exec agent minicli -l     # carga inicial
docker compose exec agent minicli -o     # observação contínua (Ctrl+C encerra)
docker compose exec agent minicli -sta   # reenvia lotes pendentes
docker compose exec agent minicli -c     # limpa o ponteiro de leitura
```

Com o `watch` ativo, logs novos ou apendados no `Log_paths/` do host chegam ao `-o` e vão para a API.

`Configuration_Files/` é montado do host em `/app/Configuration_Files` (leitura e escrita), então o `filter.yaml`, o `filestate.json` e os lotes pendentes em `API_SS.json` sobrevivem a `down`/`--build`.

---

## Roadmap

- [x] Envio da linha classificada para uma API central
- [x] Tornar o endpoint da API configurável pelo `.env`
- [x] Unificar as duas entradas num único CLI (`minicli.py`)
- [x] Oferecer uma limpeza do índice de leitura pelo CLI
- [x] Envio por batch de 100 logs
- [x] Tratar observabilidade de menos de 100 logs
- [x] Fazer disparo correto dos logs faltantes
- [x] Validar variáveis de ambiente na inicialização
- [x] Tratar truncamento do arquivo de log, reiniciando a leitura do zero
- [x] Fazer a tratativa de logs com API fora do ar
- [ ] Tratar rotação, com o arquivo renomeado ou recriado

### Correções pendentes

Levantadas em revisão do código, em ordem de severidade.

**Críticas**

- [X] Corrigir o `compose.yml`: rede única entre `agent` e `api`, bind em `0.0.0.0`, comando do agente e montagem dos diretórios de log
- [X] Gravar o `filestate.json` de forma atômica e tolerar o arquivo corrompido na leitura, para um `Ctrl+C` não impedir a próxima execução
- [X] Validar as variáveis de ambiente dentro do `MiniMim.py`, e não só pelo CLI
- [X] Só avançar o ponteiro de leitura depois do envio confirmado pela API

**Altas**

- [X] Não persistir a posição de leitura quando o `pre_filtro` levanta exceção
- [ ] Não avançar o ponteiro de um serviço que ainda não tem regras no `filter.yaml`
- [X] Respeitar o lote de 100 no `--observe`, sem despachar a cada evento multilinha
- [ ] Enviar para a API fora do lock, para não travar a thread do watchdog por até 5s
