"""
Pipeline domain exceptions.

Used by agents and LLM client to signal specific failure modes,
allowing the orchestrator to apply targeted handling (retry / degrade / fail).
"""


class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    def __init__(self, message: str, stage: str = "", details: dict = None):
        super().__init__(message)
        self.stage = stage
        self.details = details or {}


class LLMRateLimitError(PipelineError):
    """LLM provider returned 429 — retries exhausted."""
    pass


class LLMSchemaError(PipelineError):
    """LLM output failed schema validation or JSON parse."""
    pass


class LLMTimeoutError(PipelineError):
    """LLM request timed out."""
    pass


class LLMAuthError(PipelineError):
    """LLM provider returned 401/403 — API key invalid or quota exhausted."""
    pass


class RenderError(PipelineError):
    """Error during HTML→PPTX rendering or chart injection."""
    pass


class ParseError(PipelineError):
    """Error during document parsing (DOCX/XLSX/etc)."""
    pass
