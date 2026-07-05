from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.mcp.executor import init_providers
from app.routes import sessions, messages, mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register all MCP providers on startup
    init_providers()
    yield


app = FastAPI(
    title="Messaging LLM Orchestration API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(mcp.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
