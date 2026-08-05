# MiniMim

Agente leve de coleta e pré-filtragem de logs. Ele monitora um arquivo de log em tempo real, classifica cada nova linha segundo regras de expressão regular definidas pelo usuário e encaminha apenas o que interessa para um centralizador via API.

A ideia é fazer a triagem **na ponta**: em vez de mandar o log inteiro para o servidor central, o MiniMim decide localmente o que é relevante e qual o tipo do evento, reduzindo tráfego e trabalho de processamento no centralizador.

> **Referencia** - Estamos utilizando o projeto [loghub](https://github.com/logpai/loghub.git) como base de analise, todos os logs utilizados vem do repositorio


---

## Como funciona

1. **Leitura da configuração** — na inicialização, as variáveis do `.env` são carregadas, o `filter.yaml` é lido e todas as regexes são compiladas uma única vez. As regras de cada serviço são ordenadas pela `especificidade` (maior primeiro), então há um custo extra apenas na primeira rodada.
2. **Monitoramento** — o [watchdog](https://pypi.org/project/watchdog/) observa o diretório de log. A cada evento de modificação no arquivo alvo, o agente lê **apenas as linhas novas** (mantém a posição do último `read` com `seek`/`tell`), sem reprocessar o arquivo todo.
3. **Pré-filtro** — cada linha nova é testada contra as regras dos serviços habilitados. O primeiro match vence (ou seja, o padrão mais específico), a linha é classificada com o `id` da regra e a busca para ali.
4. **Envio** — a linha classificada é enviada por `POST` em JSON para o centralizador, no formato `{"servico": ..., "log": ..., "tipo": ...}`.

> **Status:** a chamada de envio (`envio_para_API`) está implementada, mas ainda comentada em `pre_filtro` — no momento o resultado da classificação é apenas impresso no console. Descomente a linha para ativar o envio.

---

## Estrutura

```
MiniMim/
├── MiniMim.py                      # agente: watchdog + pré-filtro + envio
├── ConfigurationFiles/
│   └── filter.yaml                 # regras de filtragem por serviço
├── .env                            # caminhos do ambiente (não versionado)
├── requirements.txt
└── dockerfile
```

---

## Requisitos

- Python 3.11+
- Dependências: `watchdog`, `PyYAML`, `requests`, `python-dotenv` (a lista completa do ambiente está em `requirements.txt`)

---

## Instalação

```bash
git clone git@github.com:Theo-Panella/MiniMim-Agent.git
cd MiniMim-Agent

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
```

---

## Configuração

### `.env`

Os caminhos usados pelo agente vêm de variáveis de ambiente, carregadas por [python-dotenv](https://pypi.org/project/python-dotenv/) na inicialização. O arquivo **não é versionado** (está no `.gitignore`), então crie o seu na raiz do projeto:

```dotenv
LOG_FILE_NAME = log_para_teste.txt
LOG_PATH = C:\temp\
CONFIGURATION_FILE = C:\caminho\completo\para\MiniMim\ConfigurationFiles\filter.yaml
```

| Variável | Descrição |
|---|---|
| `LOG_PATH` | diretório observado pelo watchdog — **precisa terminar com o separador** (`C:\temp\` ou `/var/log/`), porque é concatenado direto com o nome do arquivo |
| `LOG_FILE_NAME` | nome do arquivo de log dentro desse diretório |
| `CONFIGURATION_FILE` | caminho **absoluto** do `filter.yaml` |

Pontos de atenção:

- **Os nomes são case-sensitive** no Linux/Docker. O Windows tolera divergência de caixa (`os.environ` é case-insensitive lá), então um `.env` errado pode funcionar na sua máquina e quebrar no container — use sempre MAIÚSCULAS.
- **Não coloque aspas** nos valores. `LOG_PATH = "C:\temp\"` faria as aspas entrarem no caminho.
- Espaços em volta do `=` são removidos pelo dotenv, mas espaços **dentro** do valor não.
- Barras invertidas do Windows são literais aqui — não precisa escapar.
- Se qualquer uma das três variáveis faltar, `os.getenv` devolve `None` e o agente falha logo no início (`TypeError` na concatenação do caminho ou erro ao abrir o `filter.yaml`).
- `load_dotenv()` **não sobrescreve** variáveis já definidas no ambiente. Isso é proposital: no Docker, o `-e`/`--env-file` tem precedência sobre um `.env` que tenha ido junto na imagem.

### `ConfigurationFiles/filter.yaml`

As regras são agrupadas por serviço. Cada regra tem um `id` (a chave), um `padrao` (regex Python) e uma `especificidade`:

```yaml
Flask:
    admin_access_accepted:
        padrao: ' flask\[\d+\]: Accepted password for admin from .*'
        especificidade: 10
    normal_access_failed:
        padrao: ' flask\[\d+\]: Failed password for .*'
        especificidade: 1
```

Quanto maior a `especificidade`, mais cedo a regra é testada. Sempre escreva do **mais específico para o mais genérico** — no exemplo acima, um login aceito de `admin` casa com `admin_access_accepted` e nunca chega em `normal_access_accepted`.

### Serviços ativos

Apenas os serviços listados em `lista_de_servico`, no topo do `MiniMim.py`, são avaliados — mesmo que existam outros no `filter.yaml`:

```python
lista_de_servico = ['Flask']
```

### Endpoint do centralizador

Definido em `envio_para_API`, dentro do `MiniMim.py` (padrão: `http://127.0.0.1:8000`).

---

## Execução

```bash
python MiniMim.py
```

O agente fica em loop imprimindo as classificações encontradas. Encerre com `Ctrl+C` — o observer é finalizado no `finally`.

Para testar, basta acrescentar linhas ao arquivo de log monitorado:

```bash
echo "Oct 10 10:00:00 host flask[1234]: Failed password for admin from 10.0.0.5" >> C:/temp/log_para_teste.txt
```

---

## Docker

O `dockerfile` parte de `python:3`, instala o `requirements.txt` e copia o projeto para `/app`. O `CMD` padrão é `/bin/bash` — ou seja, a imagem sobe num shell e **não** executa o agente sozinho.

### Build

```bash
docker build -t minimim .
```

O `.env` **não entra na imagem** (está no `.gitignore`, mas o `COPY . .` do dockerfile não respeita `.gitignore` — só `.dockerignore`). Não conte com ele: passe a configuração em tempo de execução, como abaixo.

### Configuração dentro do container

A regra é: **os caminhos do `.env` precisam ser os caminhos de dentro do container, não os do host.** Um `CONFIGURATION_FILE = C:\Users\...` não existe no container Linux.

Crie um `.env.docker` separado:

```dotenv
LOG_FILE_NAME = log_para_teste.txt
LOG_PATH = /var/log/minimim/
CONFIGURATION_FILE = /app/ConfigurationFiles/filter.yaml
```

E rode montando o diretório de logs do host no ponto que o `LOG_PATH` aponta:

```bash
docker run -it \
  --env-file .env.docker \
  -v C:/temp:/var/log/minimim \
  minimim \
  python MiniMim.py
```

Ou passando as variáveis avulsas, sem arquivo:

```bash
docker run -it \
  -e LOG_PATH=/var/log/minimim/ \
  -e LOG_FILE_NAME=log_para_teste.txt \
  -e CONFIGURATION_FILE=/app/ConfigurationFiles/filter.yaml \
  -v C:/temp:/var/log/minimim \
  minimim \
  python MiniMim.py
```

O `python MiniMim.py` no final sobrescreve o `CMD` do dockerfile. Para que a imagem já suba executando o agente, troque a última linha do dockerfile:

```dockerfile
CMD [ "python", "MiniMim.py" ]
```

### Notas

- `CONFIGURATION_FILE` aponta para `/app/ConfigurationFiles/filter.yaml` porque o `WORKDIR` é `/app` e o `COPY . .` traz o `ConfigurationFiles/` junto. Se preferir editar as regras sem rebuildar, monte também esse diretório: `-v ./ConfigurationFiles:/app/ConfigurationFiles`.
- Em host Windows, o watchdog dentro do container depende de eventos de filesystem propagados através do bind mount — a detecção pode ser mais lenta ou não disparar. Para teste, gere os logs de dentro do próprio container.
- Se o agente enviar para o centralizador em `127.0.0.1:8000`, esse endereço aponta para o **próprio container**. Use `host.docker.internal:8000` (Docker Desktop) ou coloque os dois na mesma rede Docker.
- Um `.dockerignore` com `.venv`, `__pycache__`, `.env` e `.git` deixa o build bem mais leve — o `COPY . .` hoje leva tudo isso junto.

---

## Roadmap

- [ ] Ativar o envio para a API no `pre_filtro`
- [ ] Mover a URL do centralizador e a lista de serviços para o `.env`
- [ ] Adicionar `.dockerignore` e `CMD [ "python", "MiniMim.py" ]` no dockerfile
- [ ] Validar as variáveis de ambiente na inicialização, com erro claro se faltar alguma
- [ ] Recarregar `filter.yaml` sem reiniciar o agente
- [ ] Tratar rotação/truncamento do arquivo de log
- [ ] Buffer/retry para falhas de envio
