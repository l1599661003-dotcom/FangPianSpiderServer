from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


PLUGIN_ACTIONS = {
    "pgy_cookie_upload",
    "catalog_fetch",
    "catalog_update",
    "catalog_retry_failed",
    "catalog_update_signed",
}


class PluginRegisterRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=64)
    client_token: Optional[str] = Field(default=None, max_length=128)
    browser_type: str = Field(default="Unknown", max_length=32)
    browser_version: str = Field(default="", max_length=32)
    extension_version: str = Field(default="", max_length=32)
    user_agent: str = Field(default="", max_length=512)


class PluginCommandRequest(BaseModel):
    action: str
    client_ids: List[int] = Field(min_length=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    operator_id: int = 0
    title: str = Field(default="", max_length=128)
    trigger_source: str = Field(default="manual", max_length=32)
    trigger_rule_id: Optional[int] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in PLUGIN_ACTIONS:
            raise ValueError(f"unsupported plugin action: {value}")
        return value

    @field_validator("client_ids")
    @classmethod
    def unique_client_ids(cls, value: List[int]) -> List[int]:
        return list(dict.fromkeys(value))


class PluginRetryRequest(BaseModel):
    client_ids: Optional[List[int]] = None
    operator_id: int = 0


class PluginEvent(BaseModel):
    cmd: str
    execution_id: Optional[int] = None
    batch_id: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[float] = None
