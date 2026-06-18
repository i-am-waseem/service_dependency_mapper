"""
Planner/Executor/Synthesizer agent.

Flow:
  1. Executor runs all deterministic tools (no LLM spend).
  2. Planner decides if the graph is interesting enough to warrant LLM synthesis.
  3. Synthesizer calls the LLM with tool findings as context, returns AnalysisResult.

If GEMINI_API_KEY is not configured, the agent returns rule-only findings
with a note that LLM synthesis was skipped — the system is still useful.
"""
import re
import json
import structlog

from app.agents import tools
from app.models.graph import AnalysisResult, Finding, RiskLevel
from app.services import graph_service, llm
from app.config import settings

logger = structlog.get_logger(__name__)


async def run_analysis() -> AnalysisResult:
    logger.info("agent_analysis_start")

    # Step 1: Executor — run all deterministic tools
    findings = tools.run_all()
    logger.info("tools_complete",
                spof=len(findings["single_points_of_failure"]),
                coupling=len(findings["tight_coupling"]),
                risk=len(findings["risky_dependencies"]),
                observability=len(findings["missing_observability"]))

    graph = graph_service.get_graph()

    # Step 2: Planner — decide if LLM synthesis is warranted
    total_findings = sum(len(v) for v in findings.values())
    use_llm = bool(settings.gemini_api_key) and (
        graph.service_count > 0 and (total_findings > 0 or graph.edge_count > 2)
    )

    architectural_observations = ""
    recommendations: list[str] = []
    risk_summary = ""

    if use_llm:
        # Step 3: Synthesizer — LLM adds narrative context
        try:
            findings_serializable = {
                k: [f.model_dump() for f in v]
                for k, v in findings.items()
            }
            raw_text = await llm.analyze_dependencies(
                graph_data=graph.model_dump(),
                tool_findings=findings_serializable,
            )
            architectural_observations, recommendations, risk_summary = _parse_llm_response(raw_text)
            logger.info("llm_synthesis_complete")
        except Exception as exc:
            logger.warning("llm_synthesis_failed", error=str(exc))
            architectural_observations = _fallback_observations(findings)
            recommendations = _fallback_recommendations(findings)
            risk_summary = _fallback_risk_summary(findings)
    else:
        logger.info("llm_skipped", reason="no api key or empty graph")
        architectural_observations = _fallback_observations(findings)
        recommendations = _fallback_recommendations(findings)
        risk_summary = _fallback_risk_summary(findings)

    return AnalysisResult(
        single_points_of_failure=findings["single_points_of_failure"],
        tight_coupling=findings["tight_coupling"],
        risky_dependencies=findings["risky_dependencies"],
        missing_observability=findings["missing_observability"],
        architectural_observations=architectural_observations,
        recommendations=recommendations,
        risk_summary=risk_summary,
    )


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def _parse_llm_response(text: str) -> tuple[str, list[str], str]:
    obs_match = re.search(
        r"### Architectural Observations\s*(.*?)(?=### Recommendations|$)",
        text, re.DOTALL
    )
    rec_match = re.search(
        r"### Recommendations\s*(.*?)(?=### Risk Summary|$)",
        text, re.DOTALL
    )
    risk_match = re.search(r"### Risk Summary\s*(.*?)$", text, re.DOTALL)

    observations = obs_match.group(1).strip() if obs_match else text

    recommendations: list[str] = []
    if rec_match:
        raw_rec = rec_match.group(1).strip()
        # Strip markdown code fences if present
        raw_rec = re.sub(r"```(?:json)?\s*", "", raw_rec).strip()
        try:
            parsed = json.loads(raw_rec)
            if isinstance(parsed, list):
                recommendations = [str(r) for r in parsed if r]
        except json.JSONDecodeError:
            # Extract any complete quoted strings from a partial/truncated JSON array
            quoted = re.findall(r'"([^"]{10,})"', raw_rec)
            if quoted:
                recommendations = quoted
            else:
                # Last resort: split on newlines / bullet points
                recommendations = [
                    line.lstrip("-*•0123456789. ").strip()
                    for line in raw_rec.splitlines()
                    if len(line.strip()) > 20 and not line.strip().startswith(("{", "[", "`"))
                ]

    risk_summary = risk_match.group(1).strip() if risk_match else ""

    return observations, recommendations, risk_summary


# ---------------------------------------------------------------------------
# Rule-only fallbacks (used when LLM is unavailable)
# ---------------------------------------------------------------------------

def _fallback_observations(findings: dict[str, list[Finding]]) -> str:
    parts = []
    if findings["single_points_of_failure"]:
        names = [f.service for f in findings["single_points_of_failure"]]
        parts.append(f"Critical SPOFs detected: {', '.join(names)}.")
    if findings["tight_coupling"]:
        parts.append("Bidirectional dependencies introduce circular runtime risk.")
    if findings["missing_observability"]:
        names = [f.service for f in findings["missing_observability"]]
        parts.append(f"Observability gaps in: {', '.join(names)}.")
    if not parts:
        parts.append("No critical issues detected by automated rules.")
    return " ".join(parts)


def _fallback_recommendations(findings: dict[str, list[Finding]]) -> list[str]:
    recs = []
    if findings["single_points_of_failure"]:
        recs.append("Introduce circuit breakers and fallbacks for SPOF services.")
        recs.append("Consider replicating or caching SPOF service responses.")
    if findings["tight_coupling"]:
        recs.append("Break bidirectional dependencies by introducing an event bus or shared abstraction.")
    if findings["missing_observability"]:
        recs.append("Add /metrics (Prometheus) and structured logging to all services.")
        recs.append("Implement standardised health check endpoints (/health, /ready).")
    return recs or ["System appears healthy based on automated checks."]


def _fallback_risk_summary(findings: dict[str, list[Finding]]) -> str:
    critical = sum(
        1 for flist in findings.values()
        for f in flist if f.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    )
    return (
        f"Automated analysis found {critical} high/critical severity findings. "
        "Enable LLM synthesis (set GEMINI_API_KEY) for deeper architectural insights."
    )
