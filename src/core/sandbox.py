import ast
import resource
from pathlib import Path
from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.core.exceptions import SecurityException, ExecutionException

# Builtins estritamente seguros
SAFE_BUILTINS = {
    'abs': abs, 'round': round, 'min': min, 'max': max,
    'len': len, 'sum': sum, 'enumerate': enumerate,
    'zip': zip, 'dict': dict, 'list': list, 'tuple': tuple,
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'range': range, 'True': True, 'False': False, 'None': None,
    'any': any, 'all': all, 'set': set, 'sorted': sorted
}

BLOCKED_NODES = (
    ast.Import, ast.ImportFrom, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith
)

BLOCKED_ATTRIBUTES = {
    '__class__', '__subclasses__', '__bases__', '__globals__',
    '__code__', '__reduce__', '__mro__', 'to_sql', 'to_pickle',
    'read_pickle', 'to_csv', 'read_csv'  # Evita I/O direto via Pandas no código do LLM
}

class ASTSecurityVisitor(ast.NodeVisitor):
    def visit(self, node: ast.AST):
        if isinstance(node, BLOCKED_NODES):
            raise SecurityException(f"Nó de AST proibido detectado: {type(node).__name__}")
        return super().visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in BLOCKED_ATTRIBUTES or node.attr.startswith('_'):
            raise SecurityException(f"Acesso a atributo inseguro bloqueado: '{node.attr}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Impede chamadas perigosas como eval, exec ou invocação de builtins restritos
        if isinstance(node.func, ast.Name) and node.func.id in {'eval', 'exec', 'open', '__import__', 'compile', 'globals', 'locals'}:
            raise SecurityException(f"Invocação explícita de função perigosa: '{node.func.id}'")
        self.generic_visit(node)


class IsolatedDataEngine:
    """Executa transformações isolando limites de hardware e aplicando rollback transacional."""

    def __init__(self, memory_limit_mb: int = 2048):
        self.memory_limit_mb = memory_limit_mb

    def _set_resource_limits(self):
        if self.memory_limit_mb <= 0:
            return
        bytes_limit = self.memory_limit_mb * 1024 * 1024
        try:
            # Não baixar o limite abaixo do tamanho de memória virtual atualmente alocado pelo processo
            with open("/proc/self/status", "r") as f:
                content = f.read()
                if "VmSize:" in content:
                    vmsize_kb = int(content.split("VmSize:")[1].split()[0])
                    current_bytes = vmsize_kb * 1024
                    if bytes_limit < current_bytes * 1.2:
                        bytes_limit = int(current_bytes * 1.5)
            resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
        except (ValueError, OSError, Exception):
            pass  # Nem todos os SOs/ambientes suportam RLIMIT_AS estrito

    def validate_code_ast(self, code_str: str) -> None:
        try:
            parsed = ast.parse(code_str)
            ASTSecurityVisitor().visit(parsed)
        except SyntaxError as e:
            raise ExecutionException(f"Erro de sintaxe no código gerado pelo modelo: {str(e)}")

    def execute_transform(self, code_str: str, current_parquet: Path, output_parquet: Path) -> Tuple[bool, str, Dict[str, Any]]:
        try:
            self.validate_code_ast(code_str)
        except SecurityException as sec_err:
            return False, f"Segurança: {str(sec_err)}", {}
        except ExecutionException as exec_err:
            return False, f"Sintaxe: {str(exec_err)}", {}

        if not current_parquet.exists():
            return False, f"Arquivo de checkpoint de origem não existe: {current_parquet}", {}

        try:
            df = pd.read_parquet(current_parquet)
        except Exception as e:
            return False, f"Falha ao ler checkpoint Parquet: {str(e)}", {}

        rows_before, cols_before = df.shape
        dtypes_before = df.dtypes.astype(str).to_dict()

        # Ambiente controlado
        local_scope = {
            'df': df,
            'pd': pd,
            'np': np,
            '__builtins__': SAFE_BUILTINS
        }

        try:
            self._set_resource_limits()
            compiled_code = compile(code_str, filename="<agent_generated>", mode="exec")
            exec(compiled_code, local_scope)

            modified_df = local_scope.get('df')
            if not isinstance(modified_df, pd.DataFrame):
                raise ExecutionException("O script gerado não retornou um 'df' do tipo pandas.DataFrame.")

            output_parquet.parent.mkdir(parents=True, exist_ok=True)
            # Persiste novo checkpoint em Parquet (preserva tipos e metadados)
            modified_df.to_parquet(output_parquet, engine='pyarrow', index=False)

            rows_after, cols_after = modified_df.shape
            diff_metrics = {
                "rows_delta": rows_after - rows_before,
                "cols_delta": cols_after - cols_before,
                "current_rows": rows_after,
                "current_cols": cols_after,
                "dtypes_altered": {
                    k: str(v) for k, v in modified_df.dtypes.items()
                    if k not in dtypes_before or str(v) != dtypes_before[k]
                }
            }
            return True, "Transformação aplicada com sucesso.", diff_metrics

        except Exception as e:
            # Em caso de erro, o arquivo de destino não é salvo -> Rollback nativo
            if output_parquet.exists():
                output_parquet.unlink()
            return False, f"Falha de execução: {type(e).__name__} - {str(e)}", {}
