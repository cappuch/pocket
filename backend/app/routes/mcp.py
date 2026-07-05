"""
MCP API routes — provider listing, OAuth flow, connection management.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.mcp import oauth, token_store
from app.mcp.registry import get_provider, list_providers

router = APIRouter(prefix="/mcp", tags=["mcp"])

REDIRECT_URI = "http://localhost:8000/mcp/oauth/google/callback"


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


# --- Direct OAuth redirect handlers (for local dev without a frontend) ---

@router.get("/oauth/{provider_id}/start")
async def oauth_start(provider_id: str, user_id: str = Query(default="test-user")):
    """
    Visit this URL in your browser to start the OAuth flow.
    e.g. http://localhost:8000/mcp/oauth/google/start?user_id=test-user
    """
    redirect_uri = f"http://localhost:8000/mcp/oauth/{provider_id}/callback"
    url = oauth.get_authorize_url(provider_id, user_id, redirect_uri)
    if url is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)


@router.get("/oauth/{provider_id}/callback")
async def oauth_redirect_callback(provider_id: str, code: str = Query(...), state: str = Query(...)):
    """
    Google redirects here after the user approves.
    State format is: {user_id}:{provider_id}
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    user_id = parts[0]
    redirect_uri = f"http://localhost:8000/mcp/oauth/{provider_id}/callback"

    success = await oauth.exchange_code(
        provider_id=provider_id,
        user_id=user_id,
        code=code,
        redirect_uri=redirect_uri,
    )

    if not success:
        return HTMLResponse("<h1>Connection failed</h1><p>Token exchange failed. Check your client secret.</p>", status_code=400)

    return HTMLResponse(f"""
        <h1>Connected!</h1>
        <p>{provider_id} is now connected for user <b>{user_id}</b>.</p>
        <p>You can close this tab.</p>
    """)
