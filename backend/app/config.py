from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load ALL .env vars into os.environ so OAuth code can access them
load_dotenv()


class Settings(BaseSettings):
    nebius_api_key: str = "v1.CmQKHHN0YXRpY2tleS1lMDBkMDB4NmFmeDIycnFkYzESIXNlcnZpY2VhY2NvdW50LWUwMHB0dGozcHRxN2tnOXA0cTIMCKfGqdIGEKLz6tgDOgwIp8nBnQcQwML3xAFAAloDZTAw.AAAAAAAAAAFEtphUB-Ha-3Qy_C2IX_TUH0Deul0q2-nfo0RXe05N78uJWuvXz6mohMFvIh4Tp_c4RAC9M8l-MQqzHTOJkbwF"
    nebius_base_url: str = "https://api.studio.nebius.com/v1/"
    nebius_model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct"
    exa_api_key: str = "a2c5d4e8-4ea1-4af8-9b57-d0a3b7279963"
    redis_url: str = "redis://localhost:6379/0"
    debounce_ms: int = 2000  # coalesce burst messages within this window

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
