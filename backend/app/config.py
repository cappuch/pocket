from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    nebius_api_key: str = "v1.CmMKHHN0YXRpY2tleS1lMDBqdjM1ZnBoMDV4aDdxeXASIXNlcnZpY2VhY2NvdW50LWUwMGNzZDRrNGJ2Y3A5OWoxMDIMCOK4qdIGEKzqnLACOgsI4rvBnQcQgIqoN0ACWgNlMDA.AAAAAAAAAAG77RJ2eYahg34p76w0LbIrhdfmpY9PD4bxBPCSaEsHZKTconG52xjhVe9qVi-d3_HKAatU6wjjxsDBD3xjt8wH"
    nebius_base_url: str = "https://api.studio.nebius.com/v1/"
    nebius_model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct"
    exa_api_key: str = "704108db-bf95-4a14-ae2e-3e9ba8492b3b"
    redis_url: str = "redis://localhost:6379/0"
    debounce_ms: int = 2000  # coalesce burst messages within this window

    class Config:
        env_file = ".env"


settings = Settings()
