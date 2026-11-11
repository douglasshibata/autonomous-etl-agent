"""
Core domain exceptions for Autonomous ETL Agent Platform.
"""

class ETLException(Exception):
    """Base exception for all ETL domain errors."""
    pass

class SecurityException(ETLException):
    """Raised when AST analysis or runtime environment detects unauthorized actions."""
    pass

class ExecutionException(ETLException):
    """Raised when data transformation code fails compilation or runtime validation."""
    pass

class DataIntegrityException(ETLException):
    """Raised when data profile invariants or schema guarantees are violated."""
    pass

class ScriptExecutionException(ETLException):
    """Raised when secondary automation scripts fail or exceed resource quotas."""
    pass
