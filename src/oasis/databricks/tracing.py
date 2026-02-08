"""MLflow tracing for OASIS tool calls.

Provides citation-level transparency: every tool invocation is traced
with inputs, outputs, and timing. Traces are sent to Databricks (if
configured) or stored locally in ./mlruns.

Usage:
    from oasis.databricks.tracing import traced

    @traced
    def my_tool(query: str) -> str:
        ...  # inputs/outputs logged automatically
"""

import functools
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level state: configured once at startup
_mlflow = None
_configured = False


def _get_mlruns_dir() -> str:
    """Get an absolute path for local MLflow storage.

    Uses OASIS_DATA_DIR/mlruns if set, otherwise falls back to
    the project's oasis_data/mlruns directory. This avoids depending
    on the CWD being writable (Claude Desktop doesn't set CWD).
    """
    data_dir = os.environ.get("OASIS_DATA_DIR")
    if data_dir:
        return str(Path(data_dir) / "mlruns")
    # Fallback: next to this source file (unlikely in production)
    return str(Path(__file__).resolve().parent.parent.parent.parent / "oasis_data" / "mlruns")


def configure_tracing() -> None:
    """Set up MLflow tracking URI and experiment. Call once at startup."""
    global _mlflow, _configured

    try:
        import mlflow
    except ImportError:
        logger.info("MLflow not installed — tracing disabled")
        return

    try:
        from oasis.databricks.config import get_config

        cfg = get_config()
        if cfg.is_configured:
            mlflow.set_tracking_uri("databricks")
            logger.info("MLflow tracing → Databricks (%s)", cfg.host)
        else:
            mlruns_dir = _get_mlruns_dir()
            mlflow.set_tracking_uri(f"file://{mlruns_dir}")
            logger.info("MLflow tracing → local (%s)", mlruns_dir)

        mlflow.set_experiment("/oasis")
        _mlflow = mlflow
        _configured = True
    except Exception as e:
        logger.warning("MLflow setup failed: %s", e)


def traced(func):
    """Decorator: trace function with MLflow if available, no-op otherwise.

    Creates a full MLflow trace with inputs, outputs, and timing.
    Each call creates a new trace visible in the Databricks MLflow UI.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _configured or _mlflow is None:
            return func(*args, **kwargs)

        # mlflow.trace() as a context manager creates a proper trace
        # that shows up in search_traces()
        try:
            @_mlflow.trace(name=func.__name__)
            def _inner(*a, **kw):
                return func(*a, **kw)

            return _inner(*args, **kwargs)
        except Exception:
            # If tracing fails, still run the function
            return func(*args, **kwargs)

    return wrapper


# ------------------------------------------------------------------
# MCP tool: retrieve traces for citation transparency
# ------------------------------------------------------------------


def register_tracing_tools(mcp) -> None:
    """Register the citation trace retrieval tool with the MCP server."""

    @mcp.tool()
    def get_citation_trace(limit: int = 5) -> str:
        """Retrieve recent OASIS tool traces for citation transparency.

        Shows which data was used at each reasoning step, enabling
        row-level and step-level citations. Traces are logged to
        your Databricks workspace under the /oasis experiment.

        Args:
            limit: Maximum number of recent traces to return (default: 5).

        Returns:
            Formatted trace data with inputs, outputs, and timing per step.
        """
        if _mlflow is None:
            return (
                "**Tracing not available.** "
                "Install mlflow (`pip install mlflow`) and restart the server."
            )

        try:
            experiment = _mlflow.get_experiment_by_name("/oasis")
            if not experiment:
                return "No traces found. Run a tool first to generate traces."

            client = _mlflow.MlflowClient()
            traces = client.search_traces(
                experiment_ids=[experiment.experiment_id],
                max_results=limit,
            )

            if not traces:
                return "No traces found yet. Run a tool to generate traces."

            parts = [f"**Recent OASIS Traces** (showing up to {limit})\n"]

            for trace in traces:
                info = trace.info
                parts.append(f"**Trace:** {info.request_id}")
                parts.append(f"  Status: {info.status}")
                parts.append(f"  Timestamp: {info.timestamp_ms}")
                dur = (
                    info.execution_time_ms
                    if hasattr(info, "execution_time_ms")
                    else "N/A"
                )
                parts.append(f"  Duration: {dur}ms")

                # Show spans (tool steps)
                if trace.data and trace.data.spans:
                    for span in trace.data.spans:
                        parts.append(f"  **Step:** {span.name}")
                        if span.inputs:
                            inp = json.dumps(span.inputs, default=str)[:200]
                            parts.append(f"    Input: {inp}")
                        if span.outputs:
                            out = json.dumps(span.outputs, default=str)[:200]
                            parts.append(f"    Output: {out}")

                parts.append("---")

            return "\n".join(parts)

        except Exception as e:
            return f"**Error retrieving traces:** {e}"
