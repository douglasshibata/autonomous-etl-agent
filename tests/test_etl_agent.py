import os
import sys
import json
import pytest
import pandas as pd
import numpy as np

# Adicionar caminhos para garantir que os testes importem os módulos corretos
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.path.append(os.path.join(parent_dir, "tools"))

from tools.analyze_spreadsheet import analyze_spreadsheet, WORKING_FILE_PATH
from tools.apply_pandas_transformations import apply_pandas_transformations, validate_ast
from tools.export_data import export_data, OUTPUT_DIR
from tools.execute_automation_script import execute_automation_script, SCRIPTS_DIR
from agent_orchestrator import get_agent

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Fixture para limpar arquivos de teste gerados antes e depois de cada teste."""
    # Remover arquivos temporários se existirem
    for path in [WORKING_FILE_PATH]:
        if os.path.exists(path):
            os.remove(path)

    yield

    # Limpeza pós-teste
    for path in [WORKING_FILE_PATH]:
        if os.path.exists(path):
            os.remove(path)

def test_analyze_spreadsheet_csv():
    """Testa se a ferramenta de análise lê um CSV corretamente e salva seu estado."""
    # Criar um arquivo CSV de teste
    test_csv = os.path.join(current_dir, "test_data.csv")
    test_df = pd.DataFrame({
        'ID_Pedido': [101, 102, None],
        'Cliente': ['Cliente A', None, 'Cliente C'],
        'Valor_Bruto': ['R$ 100,00', 'R$ 200,00', 'R$ 300,00']
    })
    test_df.to_csv(test_csv, index=False)

    # Executar a análise
    result = analyze_spreadsheet.invoke({"file_path": test_csv})

    assert "RESUMO DA PLANILHA CARREGADA" in result
    assert "ID_Pedido" in result
    assert "Cliente" in result
    assert os.path.exists(WORKING_FILE_PATH)

    # Limpar arquivo de teste
    if os.path.exists(test_csv):
        os.remove(test_csv)

def test_ast_sandbox_validation_safe():
    """Testa se o validador AST permite códigos de transformação Pandas normais e seguros."""
    safe_code = (
        "df['ID_Pedido'] = df['ID_Pedido'].fillna(0)\n"
        "df['Valor'] = df['Valor'].str.replace('R$', '').astype(float)"
    )
    is_safe, error = validate_ast(safe_code)
    assert is_safe
    assert error == ""

def test_ast_sandbox_validation_unsafe_import():
    """Testa se o validador AST bloqueia o uso de 'import'."""
    unsafe_code = "import os\nos.system('echo perigo')"
    is_safe, error = validate_ast(unsafe_code)
    assert not is_safe
    assert "import" in error.lower()

def test_ast_sandbox_validation_unsafe_forbidden_name():
    """Testa se o validador AST bloqueia nomes restritos como 'eval' ou 'exec'."""
    unsafe_code = "eval('df.dropna()')"
    is_safe, error = validate_ast(unsafe_code)
    assert not is_safe
    assert "restrita" in error.lower() or "proibida" in error.lower()

def test_ast_sandbox_validation_unsafe_private_attributes():
    """Testa se o validador AST bloqueia tentativas de escape usando atributos dunder."""
    unsafe_code = "df.__class__.__subclasses__()"
    is_safe, error = validate_ast(unsafe_code)
    assert not is_safe
    assert "restrito" in error.lower() or "perigoso" in error.lower()

def test_apply_pandas_transformations_success():
    """Testa a execução de transformações Pandas válidas e a geração do diff_report."""
    # Criar um estado inicial válido
    initial_df = pd.DataFrame({
        'ID': [1, 2, None],
        'Nome': ['A', None, 'C'],
        'Salario': ['R$ 1000', 'R$ 2000', 'R$ 3000']
    })
    os.makedirs(os.path.dirname(WORKING_FILE_PATH), exist_ok=True)
    initial_df.to_csv(WORKING_FILE_PATH, index=False)

    pandas_code = (
        "df.dropna(subset=['ID'], inplace=True)\n"
        "df['Nome'] = df['Nome'].fillna('Desconhecido')\n"
        "df['Salario'] = df['Salario'].str.replace('R$ ', '').astype(int)"
    )

    result = apply_pandas_transformations.invoke({"pandas_code": pandas_code})

    assert "SUCESSO NAS TRANSFORMAÇÕES PANDAS" in result
    assert "Estrutura Anterior: 3 linhas" in result
    assert "Estrutura Atual: 2 linhas" in result

    # Verificar no disco se o estado foi atualizado corretamente
    df_after = pd.read_csv(WORKING_FILE_PATH)
    assert df_after.shape[0] == 2
    assert list(df_after['Nome']) == ['A', 'Desconhecido']
    assert list(df_after['Salario']) == [1000, 2000]

def test_export_data_json_and_csv():
    """Testa a exportação de dados para formatos CSV e JSON estruturado."""
    # Preparar estado ativo
    df = pd.DataFrame({
        'Produto': ['Celular', 'Notebook'],
        'Preco': [1500.00, 3500.00]
    })
    os.makedirs(os.path.dirname(WORKING_FILE_PATH), exist_ok=True)
    df.to_csv(WORKING_FILE_PATH, index=False)

    # Exportar para JSON
    result_json = export_data.invoke({"format_type": "json", "output_name": "test_export_file"})
    assert "SUCESSO NA EXPORTAÇÃO" in result_json
    assert "JSON" in result_json

    json_path = os.path.join(OUTPUT_DIR, "test_export_file.json")
    assert os.path.exists(json_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        exported_data = json.load(f)
    assert len(exported_data) == 2
    assert exported_data[0]['Produto'] == 'Celular'

    # Limpar exportados
    if os.path.exists(json_path):
        os.remove(json_path)

def test_export_data_sql():
    """Testa a exportação de dados com geração automática de scripts SQL CREATE e INSERT."""
    # Preparar estado ativo
    df = pd.DataFrame({
        'Código': [10, 20],
        'Nome': ['Produto A', "O'Connor's Irish Beer"], # Contém aspas simples para testar escape SQL
        'Disponível': [True, False]
    })
    os.makedirs(os.path.dirname(WORKING_FILE_PATH), exist_ok=True)
    df.to_csv(WORKING_FILE_PATH, index=False)

    result_sql = export_data.invoke({"format_type": "sql", "output_name": "test_sql", "table_name": "estoque"})

    assert "SUCESSO NA EXPORTAÇÃO" in result_sql
    sql_path = os.path.join(OUTPUT_DIR, "test_sql.sql")
    assert os.path.exists(sql_path)

    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    assert "CREATE TABLE IF NOT EXISTS estoque" in sql_content
    # Validar se aspas simples foram corretamente escapadas como ''
    assert "O''Connor''s Irish Beer" in sql_content
    assert "TRUE" in sql_content or "FALSE" in sql_content

    if os.path.exists(sql_path):
        os.remove(sql_path)

def test_execute_automation_script_security_traversal():
    """Testa se o execute_automation_script bloqueia tentativas de travessia de diretório."""
    result = execute_automation_script.invoke({"script_name": "../demo_etl_workflow.py"})
    assert "Erro de Segurança" in result
    assert "residir estritamente" in result

def test_execute_automation_script_unsupported_ext():
    """Testa se o execute_automation_script bloqueia formatos perigosos ou não suportados."""
    result = execute_automation_script.invoke({"script_name": "virus.exe"})
    assert "Erro de Segurança" in result
    assert "não suportado" in result

def test_execute_automation_script_not_found():
    """Testa se o execute_automation_script lida corretamente com arquivos inexistentes."""
    result = execute_automation_script.invoke({"script_name": "non_existent_script.py"})
    assert "Erro: O script" in result

def test_execute_automation_script_success():
    """Testa se a execução de um script secundário sob subprocesso é executada e capturada."""
    # O script upload_to_api.py já está na pasta scripts, vamos usá-lo com um arquivo JSON simulado
    mock_json = os.path.join(OUTPUT_DIR, "test_api_vendas.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(mock_json, 'w', encoding='utf-8') as f:
        json.dump([{"ID_Pedido": 999, "Cliente": "Empresa Teste", "Valor_Bruto": 150.0, "Quantidade": 2}], f)

    result = execute_automation_script.invoke({
        "script_name": "upload_to_api.py",
        "script_args": ["test_api_vendas.json"]
    })

    assert "=== RELATÓRIO DE EXECUÇÃO DO SCRIPT ===" in result
    assert "Status de Saída: SUCESSO" in result
    assert "Total de registros a serem enviados: 1" in result

    if os.path.exists(mock_json):
        os.remove(mock_json)

def test_agent_orchestrator_end_to_end():
    """Testa a execução ponta a ponta do Agente Orquestrador usando a Mock LLM offline."""
    agent = get_agent()
    # Mock LLM deve simular o fluxo sequencial completo
    inputs = {"messages": [("user", "Limpe a planilha e envie para a API.")]}

    outputs = agent.invoke(inputs)
    messages = outputs.get("messages", [])

    assert len(messages) > 0
    final_message = messages[-1]
    assert final_message.type == "ai"
    assert "FLUXO DE COMPILAÇÃO E AUTOMAÇÃO ETL COMPLETO COM SUCESSO!" in final_message.content
