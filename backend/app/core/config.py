from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All deployment-specific configuration belongs in environment variables."""

    # Do not implicitly read the deployment .env file for every Settings()
    # instance.  Callers that build an isolated config (tests, migrations,
    # one-off jobs) must get safe defaults unless they explicitly opt in.
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "恩施文博智能导览平台"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://enshi_app:change_me@localhost:5432/enshi_museum"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str | None = None
    minio_access_key: str = "change_me"
    minio_secret_key: str = "change_me"
    minio_secure: bool = False
    minio_bucket: str = "enshi-media"
    visual_reference_root: str = "/data/visual_references"
    # Local MVP protection for the separate management console. Replace with
    # school SSO/local user authentication before production deployment.
    admin_api_token: str | None = None
    # Used to sign visitor access tokens. Set a long random value in .env.
    auth_secret: str = "change_me_auth_secret"
    # Public visitor mode is useful for kiosk/demo deployments. Set to true
    # when every chat/history request must carry a valid visitor token.
    auth_required: bool = False
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    chat_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_profile_id: str | None = None
    embedding_text_template: str = "title_and_content_v2"
    reranker_api_key: str | None = None
    reranker_base_url: str | None = None
    reranker_model: str | None = None
    external_model_calls_enabled: bool = False
    embedding_indexing_enabled: bool = False
    hybrid_retrieval_enabled: bool = False
    chat_generation_enabled: bool = False
    # Provider calls must fail fast enough for the local fallback to remain
    # responsive. Repeated provider failures are short-circuited in memory.
    chat_request_timeout_seconds: int = 20
    chat_failure_threshold: int = 2
    chat_circuit_cooldown_seconds: int = 60
    # Optional phase-3 query planning. Keep disabled until the provider has
    # passed the runtime smoke test; deterministic planning remains complete.
    query_planner_model_enabled: bool = False
    web_search_enabled: bool = False
    web_search_provider: str = "tavily"
    tavily_api_key: str | None = None
    web_search_monthly_request_limit: int = 0
    web_search_max_requests_per_answer: int = 2
    web_search_allowed_domains: str = "bwg.org.cn,neac.gov.cn,wtxgj.enshi.gov.cn,wlt.hubei.gov.cn,fohb.gov.cn,ncha.gov.cn,mct.gov.cn,hubei.gov.cn,chnmuseum.cn"


@lru_cache
def get_settings() -> Settings:
    # The application singleton is the one place that loads deployment
    # configuration.  Keeping this explicit prevents a test or helper object
    # from silently inheriting external model/search switches from .env.
    return Settings(_env_file=PROJECT_ROOT / ".env")


settings = get_settings()
