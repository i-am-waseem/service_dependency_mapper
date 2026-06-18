"""
Thin wrapper around the Google Generative AI SDK (Gemini).
Handles retries and keeps all prompt construction out of the routers.

Free-tier model: gemini-flash-latest (generous RPM/TPD limits on the free API key).
Get a key at: https://aistudio.google.com/app/apikey
"""
import asyncio
import json
import structlog
from typing import Optional
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = structlog.get_logger(__name__)

_model: Optional[genai.GenerativeModel] = None


def get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                max_output_tokens=settings.gemini_max_tokens,
                temperature=0.3,
            ),
        )
    return _model


@retry(
    stop=stop_after_attempt(settings.gemini_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(GoogleAPICallError),
    reraise=True,
)
async def analyze_dependencies(graph_data: dict, tool_findings: dict) -> str:
    """
    Send graph + deterministic tool findings to Gemini and get back a
    narrative architectural analysis. Returns raw text.
    """
    prompt = _build_analysis_prompt(graph_data, tool_findings)

    logger.info("llm_request_start", model=settings.gemini_model)
    # asyncio.to_thread offloads the blocking SDK call to a thread pool so the
    # event loop stays free. Preferable to generate_content_async which has
    # compatibility issues on Python 3.9 + google-generativeai 0.8.x.
    response = await asyncio.to_thread(get_model().generate_content, prompt)
    text = response.text
    logger.info("llm_request_complete",
                finish_reason=response.candidates[0].finish_reason.name)
    return text


def _build_analysis_prompt(graph_data: dict, tool_findings: dict) -> str:
    return f"""You are reviewing a microservice dependency graph.

## Graph Summary
- Services: {graph_data.get('service_count', 0)}
- Dependencies: {graph_data.get('edge_count', 0)}

## Services
{json.dumps(graph_data.get('nodes', []), indent=2)}

## Dependencies
{json.dumps(graph_data.get('edges', []), indent=2)}

## Rule-Based Findings (already computed)
{json.dumps(tool_findings, indent=2)}

## Your Task
Based on the graph and the rule-based findings above, provide:

1. **Architectural Observations** — 3-5 concise observations about the overall system design.
   Focus on patterns, anti-patterns, and systemic risks.

2. **Recommendations** — 4-6 concrete, actionable recommendations.
   Format as a JSON array of strings under the key "recommendations".

3. **Risk Summary** — One paragraph summarizing the overall risk posture.

Format your response as:
### Architectural Observations
<text>

### Recommendations
<JSON array of strings>

### Risk Summary
<text>
"""


_SYSTEM_PROMPT = (
    "You are a principal platform engineer reviewing a microservice architecture. "
    "You are concise, technically precise, and focus on systemic risks over surface issues. "
    "You never repeat what the rule-based findings already state — you add architectural context "
    "and patterns that the rules cannot detect."
)
