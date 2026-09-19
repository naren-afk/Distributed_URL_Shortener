import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, HttpUrl

CUSTOM_ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")


class URLCreate(BaseModel):
    url: HttpUrl = Field(..., description="The original long URL to shorten")
    custom_alias: Optional[str] = Field(
        None,
        min_length=3,
        max_length=30,
        description="Optional custom alias (3-30 alphanumeric characters, dashes, underscores)",
    )
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Optional expiration in days",
    )

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not CUSTOM_ALIAS_REGEX.match(v):
                raise ValueError("Custom alias must be 3-30 characters (alphanumeric, dashes, underscores only)")
            # Reserved paths
            reserved = {"api", "health", "docs", "redoc", "openapi.json", "static", "admin", "metrics"}
            if v.lower() in reserved:
                raise ValueError(f"'{v}' is a reserved keyword and cannot be used as an alias.")
        return v


class URLResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int = 0
