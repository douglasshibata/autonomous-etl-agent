# 📘 Tutorial de Operação: Plataforma Corporativa de Data Wrangling e ETL Autônomo (v2.0)

Guia passo a passo para configuração, inicialização, execução de testes e resolução de problemas na plataforma corporativa **Autonomous ETL Agent** (`autonomous-etl-agent`).

---

## 🛠️ 1. Visão Geral e Arquitetura

A plataforma eleva scripts protótipos para uma arquitetura corporativa pronta para produção:
- **State Machine:** LangGraph com loops condicionais de auto-cura e reflexão.
- **Sandboxing:** AST Security Visitor impedindo imports, chamadas perigosas (`eval`, `exec`, `open`) e atributos dunder.
- **Armazenamento Efêmero:** Checkpoints intermediários em Apache Arrow / Parquet com suporte a rollback transacional.
- **Isolamento de Sessão:** Workspaces dedicados por UUID sob `/tmp/sessions/<session_id>`.

---

## 📋 2. Pré-requisitos do Sistema

- Python 3.11+
- Git
- pip

---

## 🚀 3. Instalação e Configuração

### Passo 1: Acessar a Pasta do Projeto
```bash
cd autonomous-etl-agent
```

### Passo 2: Instalação das Dependências
```bash
pip install -r requirements.txt
```

### Passo 3: Configuração de Variáveis de Ambiente (Opcional)
Crie ou edite o arquivo `.env`:
```ini
ENVIRONMENT=production
OPENAI_API_KEY="" # Se vazio, o agente usará o Mock determinístico offline
AGENT_MODEL="gpt-4o"
SANDBOX_MEMORY_LIMIT_MB=2048
SUBPROCESS_TIMEOUT_SECONDS=30
MAX_RETRIES=3
```

---

## 💻 4. Guia de Execução

### Execução via CLI em Produção
```bash
python3 src/main.py --input data/input/sales_report_dirty.xlsx --dispatch upload_to_api.py
```

### Execução com Sessão Customizada e Retentativas
```bash
python3 src/main.py --input data/input/sales_report_dirty.xlsx --session custom-uuid-1234 --retries 5
```

---

## 🧪 5. Testes e Validação

Execute toda a suíte de testes unitários, sandboxing e state machine:

```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

---

## 🔍 6. Resolução de Problemas (Troubleshooting)

1. **`SecurityException: Nó de AST proibido detectado`**:
   - O código gerado tentou usar `import` ou `from ... import`. O sandbox restringe transformações estritamente ao escopo das funções permitidas do DataFrame `df`.
2. **`SecurityException: Acesso a atributo inseguro bloqueado`**:
   - O código tentou acessar atributos que iniciam com `_` (dunders) ou métodos diretos de I/O (`to_csv`, `read_pickle`). As saídas devem ser delegadas aos exportadores nativos da plataforma.
3. **`MemoryError / RLIMIT_AS`**:
   - Ajuste `SANDBOX_MEMORY_LIMIT_MB` em `config/settings.py` ou via variável de ambiente `SANDBOX_MEMORY_LIMIT_MB=2048`.
