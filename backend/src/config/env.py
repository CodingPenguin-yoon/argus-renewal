from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    frontend_origin: str = "http://localhost:3000"
    news_provider: str = "mock"
    db_path: str = "data/argus.db"

    dart_sync_enabled: bool = False
    dart_api_key: Optional[str] = None
    dart_corp_code_url: str = "https://opendart.fss.or.kr/api/corpCode.xml"
    dart_disclosure_list_url: str = "https://opendart.fss.or.kr/api/list.json"
    dart_disclosure_page_count: int = 100
    dart_material_only: bool = True
    dart_material_include_patterns: str = ""
    dart_material_exclude_patterns: str = ""

    kis_master_provider: str = "disabled"
    kis_master_file_path: Optional[str] = None
    kis_base_url: str = "https://openapi.koreainvestment.com:9443"
    kis_symbol_master_path: str = "/uapi/domestic-stock/v1/quotations/search-stock-info"
    kis_symbol_master_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    kis_symbol_master_query_params_json: Optional[str] = None
    kis_symbol_master_tr_id: Optional[str] = None
    kis_app_key: Optional[str] = None
    kis_app_secret: Optional[str] = None
    kis_access_token: Optional[str] = None

    market_briefing_timeout_seconds: float = 20.0
    market_briefing_max_retries: int = 3
    market_briefing_backoff_seconds: float = 1.0
    market_briefing_signal_enabled: bool = True
    market_briefing_signal_market_scope: str = "KRX"
    market_briefing_signal_rules_json: Optional[str] = None

    kis_market_breadth_provider: str = "disabled"
    kis_market_breadth_file_path: Optional[str] = None
    kis_market_breadth_path: str = "/uapi/domestic-stock/v1/market/market-breadth"
    kis_market_breadth_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    kis_market_breadth_query_params_json: Optional[str] = None
    kis_market_breadth_field_alias_map_json: Optional[str] = None
    kis_market_breadth_tr_id: Optional[str] = None

    kis_domestic_derivatives_provider: str = "disabled"
    kis_domestic_derivatives_file_path: Optional[str] = None
    kis_domestic_derivatives_path: str = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
    kis_domestic_derivatives_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    kis_domestic_derivatives_query_params_json: Optional[str] = None
    kis_domestic_derivatives_field_alias_map_json: Optional[str] = None
    kis_domestic_derivatives_tr_id: Optional[str] = None

    kis_night_futures_provider: str = "disabled"
    kis_night_futures_file_path: Optional[str] = None
    kis_night_futures_path: str = "/uapi/overseas-futureoption/v1/quotations/night-futures"
    kis_night_futures_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    kis_night_futures_query_params_json: Optional[str] = None
    kis_night_futures_field_alias_map_json: Optional[str] = None
    kis_night_futures_tr_id: Optional[str] = None

    krx_derivatives_reference_provider: str = "disabled"
    krx_derivatives_reference_file_path: Optional[str] = None
    krx_derivatives_reference_base_url: str = "https://data.krx.co.kr"
    krx_derivatives_reference_path: str = "/api/derivatives/reference"
    krx_derivatives_reference_api_key: Optional[str] = None
    krx_derivatives_reference_response_paths: str = "output,output1,output2,items,data.items,data.rows,data"
    krx_derivatives_reference_query_params_json: Optional[str] = None
    krx_derivatives_reference_field_alias_map_json: Optional[str] = None

    fred_provider: str = "disabled"
    fred_file_path: Optional[str] = None
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    fred_observations_path: str = "/series/observations"
    fred_api_key: Optional[str] = None
    fred_timeout_seconds: float = 20.0
    fred_max_retries: int = 3
    fred_backoff_seconds: float = 1.0

    polygon_provider: str = "disabled"
    polygon_base_url: str = "https://api.polygon.io"
    polygon_api_key: Optional[str] = None
    polygon_forex_conversion_path: str = "/v1/conversion/{from}/{to}"
    polygon_forex_snapshot_path: str = "/v2/snapshot/locale/global/markets/forex/tickers"
    polygon_forex_ticker: str = "C:USDKRW"
    polygon_forex_from_symbol: str = "USD"
    polygon_forex_to_symbol: str = "KRW"
    polygon_wti_futures_enabled: bool = False
    polygon_wti_futures_symbol: Optional[str] = None
    polygon_timeout_seconds: float = 20.0
    polygon_max_retries: int = 3
    polygon_backoff_seconds: float = 1.0

    raw_ingestion_timeout_seconds: float = 20.0
    raw_ingestion_max_retries: int = 3
    raw_ingestion_backoff_seconds: float = 1.0
    raw_ingestion_descriptor_factory_paths: Optional[str] = None

    mk_rss_enabled: bool = False
    mk_rss_feed_urls: str = "https://www.mk.co.kr/rss/30100041/,https://www.mk.co.kr/rss/50200011/"

    naver_news_enabled: bool = False
    naver_news_base_url: str = "https://openapi.naver.com"
    naver_news_search_path: str = "/v1/search/news.json"
    naver_news_client_id: Optional[str] = None
    naver_news_client_secret: Optional[str] = None
    naver_news_display: int = 50
    naver_news_page_limit: int = 5
    naver_news_company_query_template: str = "{company_name} 주가 OR 공시"
    naver_news_theme_query_template: str = "{keyword} 증시"

    naver_datalab_enabled: bool = False
    naver_datalab_base_url: str = "https://openapi.naver.com"
    naver_datalab_search_path: str = "/v1/datalab/search"
    naver_datalab_client_id: Optional[str] = None
    naver_datalab_client_secret: Optional[str] = None
    naver_datalab_time_unit: str = "date"

    raw_ingestion_schedule_days: int = 1
    raw_ingestion_schedule_include_dart: bool = True
    raw_ingestion_schedule_include_market_news: bool = True
    raw_ingestion_schedule_disclosure_providers: Optional[str] = None
    raw_ingestion_schedule_market_news_providers: Optional[str] = None
    raw_ingestion_schedule_market_news_keywords: str = "주식,코스피,코스닥,환율,금리"
    raw_ingestion_automation_timezone: str = "Asia/Seoul"
    raw_ingestion_automation_weekdays: str = "0,1,2,3,4"
    raw_ingestion_automation_market_open_time: str = "09:00"
    raw_ingestion_automation_market_close_time: str = "15:30"
    raw_ingestion_automation_post_close_end_time: str = "18:00"
    raw_ingestion_automation_market_open_interval_minutes: int = 1
    raw_ingestion_automation_post_close_interval_minutes: int = 5
    raw_ingestion_automation_off_hours_interval_minutes: int = 10
    raw_ingestion_automation_holiday_dates: Optional[str] = None
    raw_ingestion_automation_normalize_include_llm: bool = False
    raw_ingestion_automation_refresh_mode: str = "smart"

    event_pipeline_enabled: bool = True
    event_pipeline_low_confidence_threshold: float = 0.55
    event_pipeline_include_llm: bool = True

    event_pipeline_llm_enabled: bool = False
    event_pipeline_llm_provider: str = "disabled"
    event_pipeline_llm_base_url: Optional[str] = None
    event_pipeline_llm_api_key: Optional[str] = None
    event_pipeline_llm_model: Optional[str] = None
    event_pipeline_llm_timeout_seconds: float = 20.0
    event_pipeline_llm_max_retries: int = 2
    event_pipeline_llm_backoff_seconds: float = 1.0

    company_report_pipeline_enabled: bool = True
    company_report_market_scope: str = "KRX"
    company_report_universe_key: str = "KRX_LARGE_CAP_CORE"
    company_report_universe_name: str = "KRX Large Cap Core"
    company_report_universe_target_size: int = 25
    company_report_seed_stock_codes: Optional[str] = None
    company_report_event_lookback_days: int = 7
    company_report_disclosure_lookback_days: int = 14
    company_report_price_lookback_days: int = 7

    company_report_llm_enabled: bool = False
    company_report_llm_provider: str = "disabled"
    company_report_llm_base_url: Optional[str] = None
    company_report_llm_api_key: Optional[str] = None
    company_report_llm_model: Optional[str] = None
    company_report_llm_timeout_seconds: float = 20.0
    company_report_llm_max_retries: int = 2
    company_report_llm_backoff_seconds: float = 1.0

    news_product_lookback_days: int = 7
    news_product_card_limit: int = 12
    news_product_representative_evidence_limit: int = 3
    news_product_refresh_ttl_seconds: int = 300
    news_product_datalab_window_days: int = 7
    news_product_batch_triage_enabled: bool = False
    news_product_batch_triage_provider: str = "disabled"
    news_product_batch_triage_base_url: Optional[str] = None
    news_product_batch_triage_api_key: Optional[str] = None
    news_product_batch_triage_model: Optional[str] = None
    news_product_batch_triage_timeout_seconds: float = 20.0
    news_product_batch_triage_max_retries: int = 2
    news_product_batch_triage_backoff_seconds: float = 1.0
    news_product_batch_triage_batch_size: int = 15
    news_product_batch_triage_upgrade_legacy_rows: bool = True
    news_product_editorial_ai_enabled: bool = False
    news_product_editorial_ai_provider: str = "disabled"
    news_product_editorial_ai_base_url: Optional[str] = None
    news_product_editorial_ai_api_key: Optional[str] = None
    news_product_editorial_ai_model: Optional[str] = None
    news_product_editorial_ai_timeout_seconds: float = 20.0
    news_product_editorial_ai_max_retries: int = 2
    news_product_editorial_ai_backoff_seconds: float = 1.0
    news_product_editorial_ai_candidate_limit: int = 8
    news_product_editorial_ai_min_editorial_score: float = 0.55

    global_events_sync_enabled: bool = True
    global_events_schedule_lookback_days: int = 7
    global_events_schedule_lookahead_days: int = 21
    global_events_release_lookback_days: int = 120
    global_events_timeout_seconds: float = 20.0
    global_events_max_retries: int = 3
    global_events_backoff_seconds: float = 1.0

    global_events_fed_calendar_url: str = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    global_events_bls_calendar_url: str = "https://www.bls.gov/schedule/news_release/bls.ics"
    global_events_bls_api_url: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    global_events_bea_schedule_url: str = "https://www.bea.gov/news/schedule"
    global_events_bea_pce_url: str = "https://www.bea.gov/data/personal-consumption-expenditures-price-index"
    global_events_ecb_calendar_url: str = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"
    global_events_boj_calendar_url: str = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"

    global_events_vendor_provider: str = "disabled"
    global_events_vendor_file_path: Optional[str] = None
    global_events_vendor_base_url: Optional[str] = None
    global_events_vendor_schedule_path: Optional[str] = None
    global_events_vendor_api_key: Optional[str] = None
    global_events_vendor_required: bool = False

    global_events_llm_enabled: bool = False
    global_events_llm_provider: str = "disabled"
    global_events_llm_base_url: Optional[str] = None
    global_events_llm_api_key: Optional[str] = None
    global_events_llm_model: Optional[str] = None
    global_events_llm_timeout_seconds: float = 20.0
    global_events_llm_max_retries: int = 2
    global_events_llm_backoff_seconds: float = 1.0

    krx_admin_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
