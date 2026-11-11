import os
import subprocess
import logging
from typing import List, Optional
from langchain_core.tools import tool

logger = logging.getLogger("ETL_Agent.execute_automation_script")

SCRIPTS_DIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts"
))

@tool
def execute_automation_script(script_name: str, script_args: Optional[List[str]] = None) -> str:
    """
    Executa com segurança scripts Python ou Bash secundários contidos exclusivamente
    na pasta de automações (ex: upload_to_api.py). O processo roda isolado,
    sem acesso ao shell geral do sistema, com timeout rígido.

    Args:
        script_name (str): O nome do arquivo do script a ser executado (ex: 'upload_to_api.py').
        script_args (List[str], opcional): Lista de argumentos adicionais de linha de comando para passar ao script.

    Returns:
        str: Relatório completo de execução contendo código de saída, stdout e stderr.
    """
    logger.info(f"Tentativa de execução de script: {script_name}")

    # Garantir que a pasta scripts existe
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    # 1. Prevenir Travessia de Diretório (Directory Traversal)
    script_path_abs = os.path.abspath(os.path.join(SCRIPTS_DIR, script_name))
    if not script_path_abs.startswith(SCRIPTS_DIR):
        logger.warning(f"Tentativa de travessia de diretório bloqueada: {script_name}")
        return "Erro de Segurança: O script solicitado deve residir estritamente dentro da pasta '/scripts'."

    # 2. Detectar e validar tipo de interpretador (Validação de tipo DEVE ocorrer antes da existência)
    ext = os.path.splitext(script_name)[1].lower()
    if ext not in ['.py', '.sh', '.bash']:
        logger.error(f"Extensão de script não suportada: {ext}")
        return f"Erro de Segurança: Formato de script '{ext}' não suportado. Apenas scripts '.py' ou '.sh'/'.bash' são permitidos."

    # 3. Verificar existência do arquivo
    if not os.path.exists(script_path_abs):
        logger.error(f"Script não encontrado: {script_path_abs}")
        return f"Erro: O script '{script_name}' não foi encontrado no diretório de automação."

    # Definir comando executável
    if ext == '.py':
        cmd = ['python3', script_path_abs]
    else:
        cmd = ['bash', script_path_abs]

    # Adicionar argumentos
    if script_args:
        cmd.extend(script_args)

    # 4. Executar com Sandboxing de subprocesso e timeout rígido
    try:
        logger.info(f"Iniciando subprocesso: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30, # Timeout rígido de 30 segundos
            cwd=SCRIPTS_DIR # Rodar no contexto do diretório de scripts
        )

        stdout_output = result.stdout or "(sem saída padrão)"
        stderr_output = result.stderr or "(sem erros detectados)"

        status = "SUCESSO" if result.returncode == 0 else "FALHA"

        report = (
            f"=== RELATÓRIO DE EXECUÇÃO DO SCRIPT ===\n"
            f"Script: {script_name}\n"
            f"Status de Saída: {status} (Código: {result.returncode})\n\n"
            f"--- SAÍDA PADRÃO (STDOUT) ---\n"
            f"{stdout_output}\n\n"
            f"--- SAÍDA DE ERROS (STDERR) ---\n"
            f"{stderr_output}\n"
            f"========================================\n"
        )
        return report

    except subprocess.TimeoutExpired as te:
        logger.error(f"Timeout atingido para execução do script: {script_name}")
        return f"Erro de Execução: O script atingiu o tempo limite de execução (timeout de 30s) e foi encerrado."
    except Exception as e:
        logger.exception(f"Erro inesperado ao rodar subprocesso.")
        return f"Erro de Execução: Falha ao rodar o script no subprocesso: {str(e)}"
