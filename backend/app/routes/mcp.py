"""
MCP API routes — provider listing, OAuth flow, connection management.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.mcp import oauth, token_store
from app.mcp.registry import get_provider, list_providers

router = APIRouter(prefix="/mcp", tags=["mcp"])


# --- Models ---

class ConnectRequest(BaseModel):
    user_id: str
    provider_id: str
    redirect_uri: str


class CallbackRequest(BaseModel):
    user_id: str
    provider_id: str
    code: str
    redirect_uri: str


class DisconnectRequest(BaseModel):
    user_id: str
    provider_id: str


# --- Endpoints ---

@router.get("/providers")
async def get_providers():
    """List all available MCP service providers."""
    providers = list_providers()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "icon": p.icon,
            "scopes": p.oauth_config.scopes,
            "tools": [{"name": t.name, "description": t.description} for t in p.tools],
        }
        for p in providers
    ]


@router.get("/providers/{provider_id}")
async def get_provider_detail(provider_id: str):
    """Get detailed info about a specific provider."""
    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {
        "id": provider.id,
        "name": provider.name,
        "description": provider.description,
        "icon": provider.icon,
        "scopes": provider.oauth_config.scopes,
        "tools": [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in provider.tools
        ],
    }


@router.post("/connect")
async def connect_provider(req: ConnectRequest):
    """
    Initiate OAuth connection. Returns the authorization URL
    the frontend should redirect the user to.
    """
    url = oauth.get_authorize_url(req.provider_id, req.user_id, req.redirect_uri)
    if url is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"authorize_url": url}


@router.post("/callback")
async def oauth_callback(req: CallbackRequest):
    """
    Exchange the OAuth authorization code for tokens.
    Called by the frontend after the user completes the OAuth flow.
    """
    success = await oauth.exchange_code(
        provider_id=req.provider_id,
        user_id=req.user_id,
        code=req.code,
        redirect_uri=req.redirect_uri,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Token exchange failed")
    return {"status": "connected", "provider_id": req.provider_id}


@router.post("/disconnect")
async def disconnect_provider(req: DisconnectRequest):
    """Revoke access and disconnect a provider for a user."""
    await token_store.revoke_token(req.user_id, req.provider_id)
    return {"status": "disconnected", "provider_id": req.provider_id}


@router.get("/connections")
async def get_connections(user_id: str = Query(...)):
    """List all connected providers for a user with their status."""
    connected = await token_store.list_connected_providers(user_id)
    all_providers = list_providers()

    result = []
    for p in all_providers:
        is_connected = p.id in connected
        valid = False
        if is_connected:
            valid = await token_store.is_token_valid(user_id, p.id)
        result.append({
            "id": p.id,
            "name": p.name,
            "icon": p.icon,
            "connected": is_connected,
            "token_valid": valid,
        })
    return result
