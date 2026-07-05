"""
MCP Provider Registry — central catalog of all available service integrations.
Each provider declares its OAuth scopes, available tools, and resources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPTool:
    """A tool that an MCP provider exposes to the LLM."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class MCPProvider:
    """A registered MCP service provider."""
    id: str
    name: str
    description: str
    icon: str  # emoji or URL
    oauth_config: OAuthConfig
    tools: list[MCPTool] = field(default_factory=list)
    scopes_required: list[str] = field(default_factory=list)


@dataclass
class OAuthConfig:
    """OAuth2 configuration for a provider."""
    authorize_url: str
    token_url: str
    client_id_env: str  # env var name for client ID
    client_secret_env: str  # env var name for client secret
    scopes: list[str]
    extra_params: dict[str, str] = field(default_factory=dict)


# --- Global registry ---

_providers: dict[str, MCPProvider] = {}


def register_provider(provider: MCPProvider) -> None:
    _providers[provider.id] = provider


def get_provider(provider_id: str) -> MCPProvider | None:
    return _providers.get(provider_id)


def list_providers() -> list[MCPProvider]:
    return list(_providers.values())


def get_tools_for_providers(provider_ids: list[str]) -> list[dict]:
    """Get OpenAI-compatible tool definitions for a set of enabled providers."""
    tools = []
    for pid in provider_ids:
        provider = _providers.get(pid)
        if not provider:
            continue
        for tool in provider.tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": f"{pid}__{tool.name}",
                    "description": f"[{provider.name}] {tool.description}",
                    "parameters": tool.parameters,
                },
            })
    return tools
