"""
Security utilities for tool result content wrapping (Phase 15).

Wraps tool results with XML boundary tags to prevent prompt injection.
External data sources (news articles, SEC filings, web search) may contain
content that could be misinterpreted as instructions by the LLM.

Applied at the _serialize_result() level in both Anthropic and OpenAI bridges,
giving uniform coverage across all tools.
"""


def wrap_tool_result(content: str, tool_name: str) -> str:
    """
    Wrap tool result with boundary tags.

    The LLM sees clear boundaries between tool data and instructions.
    System prompt reinforces that <tool_output> content is DATA only.

    Args:
        content: Serialized tool result (JSON string or text)
        tool_name: Name of the tool that produced this result

    Returns:
        Content wrapped in <tool_output> tags
    """
    return f'<tool_output tool="{tool_name}">\n{content}\n</tool_output>'