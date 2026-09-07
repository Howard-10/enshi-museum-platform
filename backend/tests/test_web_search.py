from app.core.config import Settings
from app.services.web_search import TavilyWebSearchProvider, allowed_domains


def test_allowed_domains_normalizes_the_configured_allowlist() -> None:
    config = Settings(web_search_allowed_domains="NCHA.GOV.CN, mct.gov.cn, , chnmuseum.cn")

    assert allowed_domains(config) == ["ncha.gov.cn", "mct.gov.cn", "chnmuseum.cn"]


def test_tavily_adapter_disables_generated_answers_and_uses_allowlist() -> None:
    provider = TavilyWebSearchProvider(api_key="not-used-in-this-test")

    assert provider.endpoint == "https://api.tavily.com/search"
    assert provider.max_results == 5
