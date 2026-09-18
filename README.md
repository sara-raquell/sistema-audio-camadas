# Sistema Cliente/Servidor em Camadas para Processamento de Áudio

Trabalho 3 — Arquiteturas: Sistema em Camadas. Sistema cliente/servidor em três
camadas para envio, processamento e armazenamento organizado de arquivos de áudio.

## Descrição do projeto

O sistema permite que um usuário selecione um arquivo de áudio em um computador
cliente, escolha um tipo de processamento (normalização de volume, conversão para
mono, alteração de velocidade, redução de bitrate ou conversão de formato) e envie
o arquivo para um servidor remoto via HTTP. O servidor processa o áudio com
FFmpeg, armazena o original e o processado em disco de forma organizada, registra
metadados no PostgreSQL e disponibiliza tudo de volta ao cliente — que pode
reproduzir ambas as versões e consultar o histórico de envios.

## Arquitetura

O sistema segue uma arquitetura em três camadas, rodando idealmente em dois
computadores distintos (cliente e servidor):

```
┌─────────────────────┐        HTTP        ┌──────────────────────┐        SQL        ┌────────────────┐
│   Cliente (GUI)      │  ───────────────▶  │  Servidor (API)       │  ───────────────▶ │  PostgreSQL     │
│   PySide6             │  ◀───────────────  │  FastAPI + FFmpeg     │  ◀─────────────── │  (metadados)    │
└─────────────────────┘                     └──────────────────────┘                    └────────────────┘
                                                        │
                                                        ▼
                                              Armazenamento em disco
                                        (audio.{ext}, meta.json, waveform.png)
```

- **Cliente** (`client/`): aplicação desktop em PySide6. Seleciona arquivos,
  envia requisições HTTP ao servidor, reproduz áudio (original/processado) e
  exibe histórico e informações básicas do arquivo.
- **Servidor** (`server/`): API HTTP em FastAPI. Recebe uploads, aplica
  processamento via FFmpeg, gera waveform, grava metadados no banco e expõe uma
  interface web simples para listar e reproduzir os áudios armazenados.
- **Banco de dados** (`database/`): PostgreSQL, acessado via SQLAlchemy, com a
  tabela `audios` contendo os metadados de cada arquivo processado.

## Estrutura de arquivos no servidor

```
storage/
└── AAAA/MM/DD/
    └── <uuid>/
        ├── audio.{ext}            # arquivo original
        ├── audio_processed.{ext}  # arquivo processado
        ├── meta.json              # checksum, parâmetros de processamento, tamanhos
        └── waveform.png           # forma de onda gerada automaticamente
trash/
└── <uuid>/                        # áudios excluídos, mantidos temporariamente
```

## Tecnologias

- Python 3
- FastAPI (API HTTP)
- PySide6 (cliente gráfico)
- FFmpeg (processamento de áudio)
- PostgreSQL (armazenamento de metadados)
- SQLAlchemy (ORM)

## Instruções de instalação

### Pré-requisitos

- Python 3.10+
- FFmpeg instalado e disponível no `PATH` (`ffmpeg -version` deve funcionar)
- PostgreSQL 14+ em execução (localmente ou em outra máquina da rede)

### Banco de dados

1. Crie o banco:
   ```bash
   createdb audio_system
   ```
2. Aplique o schema:
   ```bash
   psql -d audio_system -f database/schema.sql
   ```
   (Alternativamente, o servidor cria as tabelas automaticamente na primeira
   execução, via `Base.metadata.create_all`.)

### Servidor

```bash
cd server
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Configure a conexão com o banco via variáveis de ambiente (ou edite
`app/config.py`):

```bash
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=audio_system
```

### Cliente

```bash
cd client
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Instruções de execução

### Executar o servidor

```bash
cd server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API disponível em `http://<ip-do-servidor>:8000`
- Documentação interativa (Swagger) em `http://<ip-do-servidor>:8000/docs`
- Interface web de listagem/reprodução em `http://<ip-do-servidor>:8000/`

### Executar o cliente

Em outro computador (na mesma rede) ou na mesma máquina:

```bash
cd client
python3 main.py
```

Na interface, informe o endereço do servidor (ex.: `http://192.168.0.10:8000`)
no campo "Servidor" e clique em "Conectar" antes de enviar arquivos.

## Configuração do banco de dados

A tabela `audios` (ver `database/schema.sql` ou `server/app/models.py`) possui:

| Campo             | Tipo      | Descrição                                   |
|-------------------|-----------|----------------------------------------------|
| id                | UUID      | Identificador único do áudio                  |
| original_name     | VARCHAR   | Nome original do arquivo enviado               |
| original_ext      | VARCHAR   | Extensão original (.mp3, .wav, etc.)          |
| mime_type         | VARCHAR   | Tipo MIME informado pelo cliente               |
| size_bytes        | INTEGER   | Tamanho do arquivo original em bytes           |
| duration_sec      | FLOAT     | Duração do áudio em segundos                   |
| sample_rate       | INTEGER   | Taxa de amostragem (Hz)                        |
| channels          | INTEGER   | Número de canais                               |
| bitrate           | INTEGER   | Taxa de bits (bps)                             |
| processing_type   | VARCHAR   | Tipo de processamento aplicado                 |
| created_at        | TIMESTAMP | Data/hora de criação do registro               |
| path_original     | VARCHAR   | Caminho do arquivo original em disco           |
| path_processed    | VARCHAR   | Caminho do arquivo processado em disco         |

## Exemplos de processamento disponíveis

| Chave              | Descrição                              | Parâmetros extras        |
|--------------------|------------------------------------------|---------------------------|
| `normalize_volume` | Normalização de volume (EBU R128)         | —                          |
| `convert_mono`     | Conversão para mono                       | —                          |
| `change_speed`     | Alteração da velocidade de reprodução     | `speed` (0.5 a 2.0)        |
| `reduce_bitrate`   | Redução da taxa de bits                   | `bitrate` (ex.: `64k`)     |
| `convert_format`   | Conversão de formato de áudio             | `output_format` (ex.: `mp3`)|

Consulte `GET /processing-types` para obter a lista atualizada em tempo de
execução.

## Endpoints da API

| Método | Rota                          | Descrição                                  |
|--------|-------------------------------|-----------------------------------------------|
| POST   | `/audios/upload`              | Envia e processa um novo áudio                |
| GET    | `/audios`                     | Lista o histórico de áudios                    |
| GET    | `/audios/{id}`                | Detalhes de um áudio                           |
| GET    | `/audios/{id}/original`       | Baixa/reproduz o áudio original                |
| GET    | `/audios/{id}/processed`      | Baixa/reproduz o áudio processado              |
| GET    | `/audios/{id}/waveform`       | Imagem da forma de onda                        |
| DELETE | `/audios/{id}`                | Move o áudio para a lixeira (`trash/`)         |
| GET    | `/processing-types`           | Lista os tipos de processamento disponíveis    |
| GET    | `/`                           | Interface web simples (lista + player)         |

## Prints da interface

*(Adicionar aqui capturas de tela da GUI do cliente e da interface web do
servidor durante a demonstração.)*

## Prints da organização dos arquivos

*(Adicionar aqui capturas de tela da árvore de diretórios em `storage/`,
mostrando `audio.{ext}`, `meta.json` e `waveform.png`.)*

## Vídeo demonstrativo

*(Link opcional para vídeo demonstrativo do fluxo completo.)*
