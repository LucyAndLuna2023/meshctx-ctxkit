"""ctxkit — local-first context kit for agents.

Two products in one MCP server:

1. ``memory``  — cross-session memory on local disk. Survives restarts,
   never leaves the machine. No account, no cloud.
2. ``consensus`` — the same question asked across multiple models, then
   scored for agreement. Catches hallucinations that a single model
   would confidently hand you.

Everything degrades gracefully: with no API key and no browser it still
runs (memory works fully offline; consensus returns a clear, actionable
error instead of crashing).
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
