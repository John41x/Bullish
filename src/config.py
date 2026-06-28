"""Application settings loaded from YAML and environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = ROOT / "config" / "settings.yaml"
EXAMPLE_SETTINGS = ROOT / "config" / "settings.example.yaml"


class TradingHoursSettings(BaseSettings):
    start: str = "09:30"
    end: str = "16:00"
    timezone: str = "America/New_York"


class RiskSettings(BaseSettings):
    max_slippage_pct: float = 3.0
    max_contracts_per_trade: int = 5
    max_contracts_per_day: int = 20
    max_notional_usd: float = 5000.0
    duplicate_suppression_seconds: int = 30
    trading_hours: TradingHoursSettings = Field(default_factory=TradingHoursSettings)
    require_limit_orders: bool = True


class BrokerSettings(BaseSettings):
    name: str = "tradier"
    base_url: str = "https://sandbox.tradier.com/v1"


class ParserSettings(BaseSettings):
    templates_file: str = "config/alert_templates.yaml"
    default_quantity: int = 1


class KillSwitchSettings(BaseSettings):
    enabled: bool = True
    flatten_on_halt: bool = True


class ReliabilitySettings(BaseSettings):
    heartbeat_interval_seconds: int = 300
    reconciliation_interval_seconds: int = 60
    watchdog_restart_delay_seconds: int = 5


class AlertBridgeSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8765


class LoggingSettings(BaseSettings):
    log_dir: str = "logs"
    json_logs: bool = True


class SlippageJournalSettings(BaseSettings):
    enabled: bool = True
    journal_path: str = "logs/slippage_journal.jsonl"


class LivePilotSettings(BaseSettings):
    enabled: bool = False
    max_contracts: int = 1
    min_pilot_weeks: int = 2


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    parser: ParserSettings = Field(default_factory=ParserSettings)
    kill_switch: KillSwitchSettings = Field(default_factory=KillSwitchSettings)
    reliability: ReliabilitySettings = Field(default_factory=ReliabilitySettings)
    alert_bridge: AlertBridgeSettings = Field(default_factory=AlertBridgeSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    slippage_journal: SlippageJournalSettings = Field(default_factory=SlippageJournalSettings)
    live_pilot: LivePilotSettings = Field(default_factory=LivePilotSettings)

    tradier_api_key: str = Field(default="", alias="TRADIER_API_KEY")
    tradier_account_id: str = Field(default="", alias="TRADIER_ACCOUNT_ID")
    tradier_base_url: str = Field(default="", alias="TRADIER_BASE_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    alert_bridge_secret: str = Field(default="", alias="ALERT_BRIDGE_SECRET")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache
def get_settings() -> AppSettings:
    settings_path = DEFAULT_SETTINGS if DEFAULT_SETTINGS.exists() else EXAMPLE_SETTINGS
    yaml_data = _load_yaml(settings_path)
    settings = AppSettings(**yaml_data)
    if settings.tradier_base_url:
        settings.broker.base_url = settings.tradier_base_url
    return settings
