"""
OAuth2 flow handlers — generate auth URLs and exchange codes for tokens.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.mcp.registry import get_provider
from app.mcp.token_store import store_token


def get_authorize_url(provider_id: str, user_id: str, redirect_uri: str) -> str | None:
    """Generate the OAuth2 authorization URL for a provider."""
    provider = get_provider(provider_id)
    if provider is None:
        return None

    oauth = provider.oauth_config
    client_id = os.environ.get(oauth.client_id_env, "")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(oauth.scopes),
        "state": f"{user_id}:{provider_id}",
        "access_type": "offline",
        "prompt": "consent",
        **oauth.extra_params,
    }

    return f"{oauth.authorize_url}?{urlencode(params)}"


async def exchange_code(
    provider_id: str,
    user_id: str,
    code: str,
    redirect_uri: str,
) -> bool:
    """Exchange an authorization code for tokens and store them."""
    provider = get_provider(provider_id)
    if provider is None:
        return False

    oauth = provider.oauth_config
    client_id = os.environ.get(oauth.client_id_env, "")
    client_secret = os.environ.get(oauth.client_secret_env, "")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oauth.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

    if resp.status_code != 200:
        return False

    data = resp.json()
    expires_in = data.get("expires_in", 3600)

    await store_token(
        user_id=user_id,
        provider_id=provider_id,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=time.time() + expires_in,
        scopes=data.get("scope", "").split(" "),
    )
    return True


async def refresh_access_token(user_id: str, provider_id: str, refresh_token: str) -> str | None:
    """Use a refresh token to get a new access token."""
    provider = get_provider(provider_id)
    if provider is None:
        return None

    oauth = provider.oauth_config
    client_id = os.environ.get(oauth.client_id_env, "")
    client_secret = os.environ.get(oauth.client_secret_env, "")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oauth.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

    if resp.status_code != 200:
        return None

    data = resp.json()
    expires_in = data.get("expires_in", 3600)

    await store_token(
        user_id=user_id,
        provider_id=provider_id,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
        expires_at=time.time() + expires_in,
    )
    return data["access_token"]
