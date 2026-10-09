<p align="center">
  <img src="logo.png" alt="MiniMim" width="300">
</p>

<h1 align="center">MiniMim</h1>

<p align="center">
  <b>Triagem de logs na ponta.</b><br>
  Um agente leve que lê, filtra e só envia o que importa.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.14-blue">
  <img alt="Docker" src="https://img.shields.io/badge/docker-ready-2496ED">
  <img alt="Status" src="https://img.shields.io/badge/status-em%20desenvolvimento-orange">
</p>

---

## Por que o MiniMim?

Mandar todo o log de todas as máquinas para um servidor central é caro: consome rede, armazenamento e processamento, e a maior parte do que chega é ruído.

O MiniMim inverte a lógica. Ele roda **no próprio endpoint**, acompanha seus arquivos de log em tempo real e decide localmente o que é relevante, com regras de regex que você define por serviço. Só as linhas que casam com alguma regra seguem para a API central, em lotes.

- **Leve:** um processo Python, sem banco de dados e sem dependências pesadas.
- **Configurável:** uma seção no `filter.yaml` por serviço, com regras ordenadas por especificidade.
- **Resiliente:** retoma de onde parou entre execuções, trata truncamento de arquivo e guarda localmente os lotes que a API não recebeu, para reenviar depois.
- **Fácil de começar:** um tutorial interativo monta toda a configuração para você.

> Os logs de amostra vêm do projeto [loghub](https://github.com/logpai/loghub.git).

---

## Como funciona

```
 arquivos de log ──► watchdog ──► pré-filtro (regex) ──► lote de 100 ──► API central
   (por serviço)    linhas novas   regra mais específica   POST /        (api.py)
                                   vence                       │
                                                               └─ falhou? salva em API_SS.json
                                                                  e reenvia com `minicli -sta`
```

1. Na inicialização, o `.env` é carregado e validado, o `filter.yaml` é lido e o índice de posições (`STATE_FILE`) é restaurado. As regras de cada serviço são compiladas e ordenadas por `especificidade` (maior primeiro).
2. O [watchdog](https://pypi.org/project/watchdog/) observa cada diretório de `LOG_PATH`. A cada modificação, o agente lê só as linhas novas e grava a posição do último `seek`, de forma atômica, então a leitura continua de onde parou.
3. Cada linha nova é comparada com as regras do serviço deduzido do nome da pasta. O primeiro match, o mais específico, vence.
4. As linhas que casam são enviadas à API em lotes de 100 (com despacho do que sobrar na observação contínua). O ponteiro de leitura só avança depois que a API confirma o recebimento.

> O nome de cada pasta de log precisa bater com a seção do `filter.yaml` (ex.: `Apache/` ↔ `Apache:`). É assim que o agente escolhe as regras certas para cada arquivo.

---

## Estrutura

```
MiniMim/
├── minicli.py                 # CLI: tutorial, carga inicial e observação
├── MiniMim.py                 # agente principal: watchdog + pré-filtro
├── api.py                     # centralizador de logs (Flask), recebe os POSTs do agente
├── Configuration_Files/
│   ├── filter.yaml            # regras de filtragem, uma seção por serviço
│   └── filestate.json         # índice de leitura por arquivo
├── Log_paths/                 # logs de amostra, uma pasta por serviço (não versionado)
├── escreve_log_teste.py       # gera linhas de log continuamente, para teste
├── compose.yml / dockerfile   # execução em containers
├── .env.example               # modelo de configuração
└── .env                       # configuração local (não versionado)
```

---

## Começando

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1. Configure

O jeito mais rápido é o tutorial interativo, que monta o `.env` e o `filter.yaml` por perguntas:

```bash
python minicli.py -t
```

Se preferir, copie o `.env.example` e edite:

```dotenv
LOG_PATH = /caminho/para/Apache/,/caminho/para/Openssh/
CONFIGURATION_FILE = Configuration_Files/filter.yaml
STATE_DIR = Configuration_Files/
STATE_FILE = Configuration_Files/filestate.json
API_URL = http://127.0.0.1:8000
API_FILE_PATH = Configuration_Files/
API_SS_FILE = API_SS.json
```

| Variável | Para que serve |
|---|---|
| `LOG_PATH` | Lista de diretórios de log, separados por vírgula (um por serviço) |
| `CONFIGURATION_FILE` | Caminho do `filter.yaml` |
| `STATE_FILE` | Arquivo onde o índice de leitura é gravado |
| `STATE_DIR` | Diretório do `STATE_FILE`, usado para a gravação atômica (arquivo temporário + troca) |
| `API_URL` | Endereço do centralizador (`api.py`) |
| `API_FILE_PATH` / `API_SS_FILE` | Onde ficam os lotes que falharam o envio, pendentes de reenvio |

### 2. Suba a API

A API precisa estar de pé antes da coleta. O `gunicorn` só roda em Linux (ele importa `fcntl`), então no Windows use o `waitress`:

```bash
waitress-serve --host=127.0.0.1 --port=8000 api:app   # Windows
gunicorn --bind 127.0.0.1:8000 api:app                # Linux
```

> O `api.py` é, por enquanto, um receptor de teste: não tem autenticação e apenas imprime o que recebe.

### 3. Colete

```bash
python minicli.py -l     # carga inicial: lê o que já existe nos logs
python minicli.py -o     # observação contínua (Ctrl+C encerra)
```

### Comandos

| Comando | O que faz |
|---|---|
| `minicli.py -t` | Tutorial interativo de configuração |
| `minicli.py -l` | Carga inicial dos arquivos nos diretórios do `.env` |
| `minicli.py -o` | Observação contínua dos diretórios de log |
| `minicli.py -c` | Limpa o ponteiro de leitura |
| `minicli.py -sta` | Reenvia à API os lotes que falharam e ficaram salvos localmente |

Um clone novo não tem logs de amostra (`*.log` está no `.gitignore`). O `escreve_log_teste.py` cria `Log_paths/Openssh/OpenSSH_2k.log` e gera linhas continuamente nele, ótimo para ver o watchdog reagir (rode da raiz do projeto).

---

## Docker

```bash
docker compose up -d --build
```

Sobe dois serviços:

- **`api`**: expõe a porta `8000` no host e fica nas redes `public` e `iso`.
- **`agent`**: fica só na rede `iso`, que é interna, e fala com a API pelo nome do serviço (`http://api:8000`). Ele sobe com `sleep infinity` e não coleta nada sozinho; a coleta é disparada com `docker compose exec`.

O `.env` **não** é gerado dentro do container, e o `compose.yml` falha se ele não existir no host. Rode o tutorial no host antes de subir, ou renomeie `.env.example` para `.env` e rode 

```bash
python minicli.py -t
````

E ajuste os caminhos que precisam apontar para o filesystem do container (prefixo `/app/`). O `.env.example` já traz um modelo:

```dotenv
LOG_PATH = /app/Log_paths/Apache,/app/Log_paths/Openssh
CONFIGURATION_FILE = /app/Configuration_Files/filter.yaml
API_URL = http://api:8000
API_FILE_PATH = /app/Configuration_Files/
```

Antes de subir, **monte os logs no serviço `agent`**. No `compose.yml`, em `agent > volumes`, descomente a linha de exemplo e troque `[caminho_original]` pela pasta de logs do host:

```yaml
    volumes:
      - ./Configuration_Files:/app/Configuration_Files:rw
      - ./Log_paths:/app/Log_paths:ro      # linha que você descomenta e ajusta
```

O destino dentro do container (`/app/Log_paths`) precisa bater com os caminhos do `LOG_PATH` no `.env`. Sem essa linha o agente não enxerga nenhum log e a coleta termina sem enviar nada.

Com tudo no ar, dispare a coleta:

```bash
docker compose exec agent minicli -l     # carga inicial
docker compose exec agent minicli -o     # observação contínua (Ctrl+C encerra)
docker compose exec agent minicli -sta   # reenvia lotes pendentes
docker compose exec agent minicli -c     # limpa o ponteiro de leitura
```

`Configuration_Files/` é montado do host em `/app/Configuration_Files` (leitura e escrita), então o `filter.yaml`, o `filestate.json` e os lotes pendentes em `API_SS.json` sobrevivem a `down` e `--build`.

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
- [ ] Implementar Autenticação na API

### Correções pendentes

Levantadas em revisão do código, em ordem de severidade.

**Críticas**

- [X] Corrigir o `compose.yml`: rede única entre `agent` e `api`, bind em `0.0.0.0`, comando do agente e montagem dos diretórios de log
- [X] Gravar o `filestate.json` de forma atômica e tolerar o arquivo corrompido na leitura, para um `Ctrl+C` não impedir a próxima execução
- [X] Validar as variáveis de ambiente dentro do `MiniMim.py`, e não só pelo CLI
- [X] Só avançar o ponteiro de leitura depois do envio confirmado pela API
- [ ] Adicionar JWT a autenticação da API
- [ ] Trafego HTTPs entre Endpoint e API

**Altas**

- [X] Não persistir a posição de leitura quando o `pre_filtro` levanta exceção
- [ ] Não avançar o ponteiro de um serviço que ainda não tem regras no `filter.yaml`
- [X] Respeitar o lote de 100 no `--observe`, sem despachar a cada evento multilinha
- [ ] Enviar para a API fora do lock, para não travar a thread do watchdog por até 5s
- [ ] Criptografar senha de acesso em ambas as pontas (endpoint e API), precisa trafegar já criptografada

**Futuro (aguardar servidor de analise)**
- [ ] Enviar para o servidor pronto para analise e indexação