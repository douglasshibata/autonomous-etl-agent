import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from src.core.exceptions import ScriptExecutionException, SecurityException

logger = logging.getLogger("ETL_Agent.runner")

ALLOWED_EXTENSIONS = {'.py', '.sh', '.bash'}

class SafeSubprocessRunner:
    """Executa scripts de automação de forma contida e segura com timeouts e quotas."""

    def __init__(self, allowed_directory: Path, timeout_seconds: int = 30):
        self.allowed_directory = Path(allowed_directory).resolve()
        self.timeout_seconds = timeout_seconds

    def run_script(
        self,
        script_name: str,
        script_args: Optional[List[str]] = None
    ) -> Tuple[int, str, str]:
        """
        Executa script contido no diretório autorizado.
        Retorna (returncode, stdout, stderr).
        """
        self.allowed_directory.mkdir(parents=True, exist_ok=True)

        # 1. Directory Traversal Guard
        script_path = (self.allowed_directory / script_name).resolve()
        try:
            script_path.relative_to(self.allowed_directory)
        except ValueError:
            raise SecurityException(
                f"Tentativa de travessia de diretório bloqueada: '{script_name}' escapa de '{self.allowed_directory}'"
            )

        # 2. Extension check
        if script_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise SecurityException(
                f"Formato de script '{script_path.suffix}' não suportado. Permitidos: {ALLOWED_EXTENSIONS}"
            )

        # 3. File existence
        if not script_path.exists():
            raise FileNotFoundError(f"Script de automação não encontrado: {script_path}")

        # 4. Command assembly
        if script_path.suffix.lower() == '.py':
            cmd = ['python3', str(script_path)]
        else:
            cmd = ['bash', str(script_path)]

        if script_args:
            cmd.extend(script_args)

        # 5. Process execution
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(self.allowed_directory)
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        except subprocess.TimeoutExpired as te:
            raise ScriptExecutionException(
                f"O script '{script_name}' excedeu o tempo limite de execução ({self.timeout_seconds}s) e foi abortado."
            ) from te
        except Exception as e:
            raise ScriptExecutionException(f"Erro ao executar subprocesso: {str(e)}") from e
