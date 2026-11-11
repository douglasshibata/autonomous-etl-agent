# 🛠️ Plataforma Corporativa de Data Wrangling e ETL Autônomo (v2.0)

Plataforma corporativa de **Engenharia de Dados e ETL Autônomo** pronta para produção em Python 3.11+. O sistema utiliza uma Máquina de Estados Cognitiva no **LangGraph** com autorreparo (self-healing feedback loops), isolamento de execução em sandbox AST avançado com limites de recursos (`resource.setrlimit`), isolamento de workspaces por sessão (`UUID`), persistência intermediária em **Apache Arrow / Parquet** e exportadores transacionais parametrizados com auditoria estruturada.

---

## 🏛️ 1. Arquitetura do Sistema (v2.0)

```text
                               +--------------------------------------------+
                               |     Ingestão de Arquivo / API Gateway      |
                               +---------------------+----------------------+
                                                     |
                                                     v
                               +---------------------+----------------------+
                               |    Workspace Isolation (UUID Session)      |
                               |    - Cria sandbox efêmero em /tmp/sessions |
                               +---------------------+----------------------+
                                                     |
                                                     v
                         +---------------------------+----------------------------+
                         |           LangGraph Cognitive State Machine            |
                         |                                                        |
                         |  [Analyze] ──► [Plan Transforms] ──► [Isolated Engine] |
                         |     ▲                                        │         |
                         |     │             Feedback de Erro           │         |
                         |     └────────────────────────────────────────┘         |
                         |                                                        |
                         |  [Validate Invariants] ──► [Export & Dispatch Script]  |
                         +---------------------------+----------------------------+
                                                     |
                                                     v
                               +---------------------+----------------------+
                               |      Audit Trail & Parquet Checkpoints     |
                               |      - Logs de auditoria estruturados JSON |
                               +--------------------------------------------+
```

### Principais Diferenciais da Versão 2.0:
1. **Eliminação de Race Conditions:** Abandono de `current_state.csv` global. Toda execução opera em `/tmp/sessions/<session_id>/` com checkpoints individuais em Parquet.
2. **Preservação Total de Tipos Primitivos:** Armazenamento intermediário em Apache Arrow / Parquet, preservando `datetime`, `category`, inteiros nulos e booleanos sem degradação para strings.
3. **Sandbox AST com Process Guard & Rollback:** AST Visitor com verificação de imports, atributos dunders e chamadas perigosas (`eval`, `exec`, `open`), com restauração atômica do estado anterior se uma transformação falhar.
4. **Ciclo de Feedback e Auto-Cura (Self-Healing Loop):** Erros de execução Pandas são capturados e roteados de volta ao nó de planejamento com reflexão (`retry_count < max_retries`).
5. **Exportação Segura e Parametrizada:** Geração de scripts SQLite DDL/DML determinísticos via `iterdump` prevenindo SQL Injection, JSON com carimbos ISO 8601, Parquet, CSV e XML.
6. **Automação Auditada e Assinada:** Execução de scripts secundários (`SafeSubprocessRunner`) com contenção de diretório, verificação de extensões autorizadas e assinatura criptográfica HMAC-SHA256.

---

## 📂 2. Estrutura de Diretórios Refatorada

```text
autonomous-etl-agent/
├── pyproject.toml                     # Metadados e dependências fixadas
├── requirements.txt                   # Dependências pip
├── config/
│   ├── __init__.py
│   └── settings.py                   # Pydantic BaseSettings (timeouts, quotas, paths)
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── state.py                  # TypedDict e modelos de estado do LangGraph
│   │   ├── sandbox.py                # Sandbox com isolamento (Restricted Python/Process Guard)
│   │   └── exceptions.py             # Exceções tipadas do pipeline
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── analyzer.py               # Profiling de dados com Arrow/Polars/Pandas
│   │   ├── transformer.py            # Execução de transformações com Rollback
│   │   ├── exporter.py               # Exporters transacionais (Parquet, SQL, JSON, XML)
│   │   └── runner.py                 # Subprocess Runner seguro com contenção de path
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── builder.py                # Compilação do grafo LangGraph com loops de retry
│   │   └── nodes.py                  # Implementação de nós (Reasoning, Reflection, Exec)
│   └── main.py                       # CLI e Entrypoint de produção
├── scripts/
│   └── upload_to_api.py              # Script modelo assinado e auditado (HMAC-SHA256)
├── tests/
│   ├── test_security_sandbox.py      # Testes de tentativa de escape e injeção
│   ├── test_state_machine.py         # Testes de autorreparo e convergência do grafo
│   ├── test_exporters.py             # Testes de geração SQL/Parquet/JSON/XML
│   └── test_etl_agent.py             # Testes de regressão e ferramentas legado
└── README.md
```

---

## 🔒 3. Checklist de Segurança em Produção

| Vetor de Risco | Mitigação Implementada |
|---|---|
| **Execução de Código Arbitrário** | `ASTSecurityVisitor` bloqueando nós de I/O, imports, dunders (`__class__`, etc.) e system calls. |
| **Sobrecarga de Hardware (DoS)** | Limite de memória virtual via `resource.setrlimit(RLIMIT_AS)` e timeout de subprocesso. |
| **Vazamento e Colisão de Dados** | Checkpoints efêmeros em diretórios com nomes baseados em `UUIDv4` por requisição em `/tmp/sessions/`. |
| **SQL Injection nas Exportações** | Uso de transações com DDL/DML compilados via `sqlite3.iterdump` e parâmetros preparados. |
| **Directory Traversal em Scripts** | Resolução estrita de caminhos canônicos (`Path.resolve()`) dentro de boundary permitida em `/scripts/`. |
| **Tampering de Dados Exportados** | Assinatura HMAC-SHA256 do payload JSON nos scripts de automação. |

---

## 🚀 4. Instalação e Execução

### Pré-requisitos
* Python 3.11+
* pip

### Instalação de Dependências
```bash
pip install -r autonomous-etl-agent/requirements.txt
```

### Executando o Pipeline via CLI
```bash
cd autonomous-etl-agent
python3 src/main.py --input data/input/sales_report_dirty.xlsx --dispatch upload_to_api.py
```

Argumentos suportados:
* `--input`, `-i`: Caminho do arquivo de dados (.csv, .xlsx, .parquet).
* `--session`, `-s`: ID de sessão customizado (UUID).
* `--retries`, `-r`: Número máximo de tentativas de autorreparo (padrão: 3).
* `--dispatch`, `-d`: Script para disparar após exportação (ex: `upload_to_api.py`).
* `--dispatch-args`: Argumentos adicionais para o script despachado.

---

## 🧪 5. Execução dos Testes Automatizados

Para rodar todos os testes unitários e de integração:

```bash
PYTHONPATH=autonomous-etl-agent python3 -m pytest autonomous-etl-agent/tests/ -v
```

A suíte valida:
1. `test_security_sandbox.py`: Bloqueio de imports, dunders, chamadas perigosas (`open`, `eval`, `exec`) e I/O direto via Pandas.
2. `test_state_machine.py`: Ciclos de autorreparo e convergência do grafo com Mock LLM de reflexão e término sob limite de retentativas.
3. `test_exporters.py`: Integridade de Parquet, ISO 8601 em JSON, escaping de SQL e XML.
4. `test_etl_agent.py`: Compatibilidade com fluxos legados e validações complementares.
