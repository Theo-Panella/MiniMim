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
├── Apache/, Openssh/          # pastas de log de amostra, uma por serviço
├── escreve_log_teste.py       # gera linhas de log continuamente, pra teste
└── .env                       # configuração local (não versionado)
```

O nome de cada pasta de log precisa bater com a seção correspondente no `filter.yaml` (ex: `Apache/` ↔ `Apache:`) — é assim que o agente escolhe as regras certas para cada arquivo.

> `legacy/MiniMim.py` é a versão original, de um único serviço/arquivo. `MiniMim.py` é a versão atual.

---

## Como funciona

1. Na inicialização, o `.env` é carregado, o `filter.yaml` é lido e o índice de posições em `JSON_PATH` é restaurado; as regras de cada serviço são compiladas e ordenadas por `especificidade` (maior primeiro).
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
JSON_PATH = Configuration_Files/filestate.json
```

`LOG_PATH` é uma lista de diretórios (um por serviço); `CONFIGURATION_FILE` aponta pro `filter.yaml`; `JSON_PATH` é onde o índice de leitura é gravado. O tutorial grava as três.

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

`escreve_log_teste.py` gera linhas de teste continuamente em `Openssh/OpenSSH_2k.log`, útil pra ver o watchdog reagir. Encerre qualquer processo com `Ctrl+C`.

A API que recebe os logs precisa estar de pé antes da coleta. O `gunicorn` só roda em Linux — ele importa `fcntl` —, então no Windows use o `waitress`:

```bash
waitress-serve --host=127.0.0.1 --port=8000 api:app   # Windows
gunicorn --bind 127.0.0.1:8000 api:app                # Linux
```

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
- [ ] Fazer a tratativa de logs com API fora do ar
- [ ] Tratar rotação, com o arquivo renomeado ou recriado

### Correções pendentes

Levantadas em revisão do código, em ordem de severidade.

**Críticas**

- [ ] Corrigir o `compose.yml`: rede única entre `agent` e `api`, bind em `0.0.0.0`, comando do agente e montagem do `.env` e dos diretórios de log
- [ ] Gravar o `filestate.json` de forma atômica e tolerar o arquivo corrompido na leitura, para um `Ctrl+C` não impedir a próxima execução
- [ ] Validar as variáveis de ambiente dentro do `MiniMim.py`, e não só pelo CLI
- [ ] Só avançar o ponteiro de leitura depois do envio confirmado pela API

**Altas**

- [ ] Não persistir a posição de leitura quando o `pre_filtro` levanta exceção
- [ ] Não avançar o ponteiro de um serviço que ainda não tem regras no `filter.yaml`
- [ ] Respeitar o lote de 100 no `--observe`, sem despachar a cada evento multilinha
- [ ] Enviar para a API fora do lock, para não travar a thread do watchdog por até 5s
