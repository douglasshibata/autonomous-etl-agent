import os
import ast
import logging
import builtins
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from langchain_core.tools import tool

logger = logging.getLogger("ETL_Agent.apply_pandas_transformations")

WORKING_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "current_state.csv"
)

def validate_ast(code_str: str) -> Tuple[bool, str]:
    """
    Valida se o código Python fornecido é seguro para execução usando a árvore de sintaxe abstrata (AST).
    Bloqueia importações, acesso a atributos privados, e nomes proibidos como eval, exec, etc.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Erro de sintaxe no código Python: {str(e)}"

    forbidden_names = {
        'eval', 'exec', 'open', '__import__', 'globals', 'locals',
        'getattr', 'setattr', 'delattr', 'pickle', 'shutil', 'sys',
        'os', 'subprocess', 'socket', 'requests', 'builtins', 'compile'
    }

    forbidden_attributes = {
        '__class__', '__subclasses__', '__globals__', '__code__',
        'system', 'popen', 'spawn', 'fork', 'read', 'write'
    }

    for node in ast.walk(tree):
        # Impedir qualquer importação
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "Uso ilegal de 'import' detectado. Não é permitido importar módulos adicionais."

        # Impedir uso de nomes perigosos
        if isinstance(node, ast.Name):
            if node.id in forbidden_names:
                return False, f"Uso de função ou variável restrita/proibida detectada: '{node.id}'."

        # Impedir acesso a atributos privados e métodos de escape de sandbox
        if isinstance(node, ast.Attribute):
            if node.attr in forbidden_attributes or node.attr.startswith('__'):
                return False, f"Acesso ao atributo restrito ou potencialmente perigoso detectado: '{node.attr}'."

    return True, ""

@tool
def apply_pandas_transformations(pandas_code: str) -> str:
    """
    Executa transformações lógicas baseadas em código Pandas de forma segura em cima
    do DataFrame carregado no estado de trabalho atual, gerando um log de alterações meticuloso.

    Args:
        pandas_code (str): Código Python contendo as operações Pandas a serem aplicadas no DataFrame `df`.
                           Exemplo:
                           df['Valor'] = df['Valor'].fillna(0)
                           df['Nome_Completo'] = df['Nome'] + ' ' + df['Sobrenome']
                           df.drop(columns=['Nome', 'Sobrenome'], inplace=True)

    Returns:
        str: Log descritivo com as diferenças detalhadas antes e depois da transformação.
    """
    logger.info("Iniciando a aplicação de transformações com Pandas.")

    if not os.path.exists(WORKING_FILE_PATH):
        return "Erro: Nenhuma planilha foi carregada ainda. Use a ferramenta 'analyze_spreadsheet' primeiro."

    # Validação de segurança AST
    is_safe, error_msg = validate_ast(pandas_code)
    if not is_safe:
        logger.warning(f"Código bloqueado pelo validador AST: {error_msg}")
        return f"Bloqueio de Segurança AST: {error_msg}"

    try:
        # Carregar o estado atual
        df_before = pd.read_csv(WORKING_FILE_PATH)
        df = df_before.copy()

        # Guardar metadados iniciais para cálculo do diff
        shape_before = df_before.shape
        cols_before = list(df_before.columns)
        nulls_before = df_before.isnull().sum().to_dict()
        dtypes_before = df_before.dtypes.apply(str).to_dict()

        # Preparar ambiente restrito (Defense in Depth)
        safe_builtins_dict = {}
        allowed_builtins = [
            'str', 'int', 'float', 'bool', 'len', 'range', 'dict', 'list', 'set',
            'tuple', 'any', 'all', 'sum', 'round', 'abs', 'min', 'max',
            'enumerate', 'zip', 'map', 'filter', 'slice'
        ]
        for name in allowed_builtins:
            if hasattr(builtins, name):
                safe_builtins_dict[name] = getattr(builtins, name)

        # Contexto de variáveis
        local_vars = {
            'df': df,
            'pd': pd,
            'np': np
        }
        global_vars = {
            '__builtins__': safe_builtins_dict
        }

        # Executar código
        logger.info(f"Executando código Pandas no DataFrame:\n{pandas_code}")
        # Compilar primeiro para validação completa e rastreamento
        compiled_code = compile(pandas_code, "<pandas_transformation>", "exec")
        exec(compiled_code, global_vars, local_vars)

        # Extrair DataFrame resultante
        df_after = local_vars.get('df')
        if not isinstance(df_after, pd.DataFrame):
            return "Erro: O código executado não manteve 'df' como um DataFrame válido do Pandas."

        # Calcular Diff Meticuloso
        shape_after = df_after.shape
        cols_after = list(df_after.columns)
        nulls_after = df_after.isnull().sum().to_dict()
        dtypes_after = df_after.dtypes.apply(str).to_dict()

        # Analisar mudanças de colunas
        added_cols = [c for c in cols_after if c not in cols_before]
        removed_cols = [c for c in cols_before if c not in cols_after]

        # Analisar mudanças em tipos de dados e nulos
        changes_summary = []
        for c in cols_after:
            col_logs = []
            if c in cols_before:
                # Mudança de Tipo
                if dtypes_before[c] != dtypes_after[c]:
                    col_logs.append(f"tipo alterado de {dtypes_before[c]} para {dtypes_after[c]}")
                # Mudança de Nulos
                if nulls_before[c] != nulls_after[c]:
                    col_logs.append(f"valores nulos mudaram de {nulls_before[c]} para {nulls_after[c]}")
            else:
                col_logs.append(f"nova coluna criada (tipo: {dtypes_after[c]}, {nulls_after[c]} nulos)")

            if col_logs:
                changes_summary.append(f" - Coluna '{c}': {', '.join(col_logs)}")

        for c in removed_cols:
            changes_summary.append(f" - Coluna '{c}': removida do DataFrame")

        # Salvar o estado atualizado de volta no disco
        df_after.to_csv(WORKING_FILE_PATH, index=False)
        logger.info(f"Transformações executadas com sucesso. Novo estado salvo em {WORKING_FILE_PATH}")

        # Construir relatório de diff detalhado
        diff_report = (
            f"=== SUCESSO NAS TRANSFORMAÇÕES PANDAS ===\n"
            f"Estrutura Anterior: {shape_before[0]} linhas x {shape_before[1]} colunas\n"
            f"Estrutura Atual: {shape_after[0]} linhas x {shape_after[1]} colunas\n\n"
            f"--- LOG DETALHADO DE ALTERAÇÕES ---\n"
            f"Colunas Adicionadas: {added_cols if added_cols else 'Nenhuma'}\n"
            f"Colunas Removidas: {removed_cols if removed_cols else 'Nenhuma'}\n"
            f"Alterações de Conteúdo/Esquema:\n"
            f"{chr(10).join(changes_summary) if changes_summary else 'Nenhuma alteração estrutural detectada.'}\n"
            f"=========================================\n"
        )
        return diff_report

    except Exception as e:
        logger.exception("Falha durante a execução de transformações Pandas.")
        return f"Erro de execução no script Pandas: {str(e)}"
