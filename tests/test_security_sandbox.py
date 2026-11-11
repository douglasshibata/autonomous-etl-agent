import pytest
from pathlib import Path
from src.core.sandbox import IsolatedDataEngine
from src.core.exceptions import SecurityException, ExecutionException

@pytest.fixture
def engine():
    return IsolatedDataEngine(memory_limit_mb=1024)

def test_block_import_statements(engine):
    malicious_code = "import os; os.system('ls')"
    with pytest.raises(SecurityException, match="Nó de AST proibido"):
        engine.validate_code_ast(malicious_code)

def test_block_import_from(engine):
    malicious_code = "from os import system; system('ls')"
    with pytest.raises(SecurityException, match="Nó de AST proibido"):
        engine.validate_code_ast(malicious_code)

def test_block_dunder_traversal(engine):
    malicious_code = "df.__class__.__subclasses__()"
    with pytest.raises(SecurityException, match="Acesso a atributo inseguro bloqueado"):
        engine.validate_code_ast(malicious_code)

def test_block_open_and_eval(engine):
    malicious_code = "f = open('/etc/passwd', 'r')"
    with pytest.raises(SecurityException, match="Invocação explícita de função perigosa"):
        engine.validate_code_ast(malicious_code)

def test_block_eval_call(engine):
    malicious_code = "eval('1 + 1')"
    with pytest.raises(SecurityException, match="Invocação explícita de função perigosa"):
        engine.validate_code_ast(malicious_code)

def test_block_exec_call(engine):
    malicious_code = "exec('df = None')"
    with pytest.raises(SecurityException, match="Invocação explícita de função perigosa"):
        engine.validate_code_ast(malicious_code)

def test_block_direct_io_attributes(engine):
    malicious_code = "df.to_csv('/tmp/leaked.csv')"
    with pytest.raises(SecurityException, match="Acesso a atributo inseguro bloqueado"):
        engine.validate_code_ast(malicious_code)

def test_block_read_pickle(engine):
    malicious_code = "df.read_pickle('/tmp/malicious.pkl')"
    with pytest.raises(SecurityException, match="Acesso a atributo inseguro bloqueado"):
        engine.validate_code_ast(malicious_code)

def test_syntax_error_handling(engine):
    invalid_syntax = "df = df.[invalid_syntax"
    with pytest.raises(ExecutionException, match="Erro de sintaxe"):
        engine.validate_code_ast(invalid_syntax)
