from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    frontend_origin: str = "http://localhost:3000"
    db_path: str = "data/argus.db"

    kis_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_token_path: str = "/oauth2/tokenP"
    kis_token_cache_path: str = "data/kis_token_cache.json"
    kis_app_key: Optional[str] = None
    kis_app_secret: Optional[str] = None

    market_briefing_timeout_seconds: float = 20.0
    market_briefing_max_retries: int = 3
    market_briefing_backoff_seconds: float = 1.0

    kis_domestic_derivatives_provider: str = "disabled"
    kis_domestic_derivatives_file_path: Optional[str] = None
    kis_domestic_derivatives_path: str = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
    kis_domestic_derivatives_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    kis_domestic_derivatives_query_params_json: Optional[str] = None
    kis_domestic_derivatives_field_alias_map_json: Optional[str] = None
    kis_domestic_derivatives_tr_id: Optional[str] = None

    kis_option_chain_provider: str = "disabled"
    kis_option_chain_file_path: Optional[str] = None
    kis_option_chain_path: str = "/uapi/domestic-futureoption/v1/quotations/display-board-callput"
    kis_option_chain_response_paths: str = "option_levels,levels,items,output,output1,output2,data.items,data.rows,data"
    kis_option_chain_query_params_json: Optional[str] = None
    kis_option_chain_field_alias_map_json: Optional[str] = None
    kis_option_chain_tr_id: Optional[str] = "FHPIF05030100"
    kis_option_chain_expiry_month: Optional[str] = None
    kis_option_list_path: str = "/uapi/domestic-futureoption/v1/quotations/display-board-option-list"
    kis_option_list_response_paths: str = "output,data.items,data.rows,data"
    kis_option_list_query_params_json: Optional[str] = None
    kis_option_list_tr_id: Optional[str] = "FHPIO056104C0"
    kis_option_chain_expected_level_count: int = 0
    kis_option_chain_stale_after_seconds: int = 300

    argus_market_reaction_provider: str = "mock"
    argus_market_reaction_file_path: Optional[str] = None
    argus_market_reaction_index_price_path: str = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
    argus_market_reaction_index_price_tr_id: str = "FHPUP02100000"
    argus_market_reaction_category_price_path: str = "/uapi/domestic-stock/v1/quotations/inquire-index-category-price"
    argus_market_reaction_category_price_tr_id: str = "FHPUP02140000"
    argus_market_reaction_investor_time_path: str = "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market"
    argus_market_reaction_investor_time_tr_id: str = "FHPTJ04030000"
    argus_market_reaction_investor_amount_multiplier: float = 10000.0
    argus_market_reaction_sector_limit: int = 3

    argus_news_triggers_provider: str = "mock"
    argus_news_triggers_file_path: Optional[str] = None
    argus_news_triggers_rss_urls: str = "https://www.mk.co.kr/rss/30100041/,https://www.mk.co.kr/rss/50200011/"
    argus_news_triggers_query: str = "금리,환율,반도체,코스피,선물,옵션"
    argus_news_triggers_limit: int = 8
    argus_news_triggers_lookback_hours: int = 24
    argus_news_ai_provider: str = "disabled"
    argus_news_ai_base_url: str = "https://api.openai.com"
    argus_news_ai_chat_path: str = "/v1/chat/completions"
    argus_news_ai_model: Optional[str] = None
    argus_news_ai_api_key: Optional[str] = None
    argus_gemini_model: Optional[str] = None
    argus_gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    argus_news_ai_timeout_seconds: float = 20.0
    argus_macro_events_provider: str = "disabled"
    argus_macro_events_file_path: Optional[str] = None

    argus_news_naver_client_id: Optional[str] = None
    argus_news_naver_client_secret: Optional[str] = None
    argus_news_naver_base_url: str = "https://openapi.naver.com"
    argus_news_naver_search_path: str = "/v1/search/news.json"
    argus_news_naver_display: int = 20
    argus_news_naver_page_limit: int = 2

    argus_disclosure_dart_api_key: Optional[str] = None
    argus_disclosure_dart_base_url: str = "https://opendart.fss.or.kr"
    argus_disclosure_dart_list_path: str = "/api/list.json"
    argus_disclosure_dart_corp_cls: str = "Y,K"
    argus_disclosure_dart_pblntf_ty: str = "B,I"
    argus_disclosure_dart_lookback_days: int = 1
    argus_disclosure_dart_page_count: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
