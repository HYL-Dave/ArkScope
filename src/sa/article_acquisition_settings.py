"""Profile-owned article acquisition policy, independent of retention."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from src.data_source_routing import DataSourcePolicyFailure, read_setting


ARTICLE_SETTINGS_KEY = "data_sources.sa_article_acquisition.settings"
SelectionLimit = Annotated[StrictInt, Field(ge=0, lt=2**53)]


class ArticleAcquisitionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_articles_per_job: SelectionLimit = 0
    body_scope: Literal["all_retained", "current"] = "all_retained"
    body_lookback_days: SelectionLimit = 0
    comment_scope: Literal["current", "tracked"] = "current"


def parse_article_settings(raw: str | None) -> ArticleAcquisitionSettings:
    if raw is None:
        return ArticleAcquisitionSettings()
    try:
        return ArticleAcquisitionSettings.model_validate_json(raw, strict=True)
    except (ValidationError, TypeError, ValueError) as exc:
        raise DataSourcePolicyFailure("sa_article_settings_invalid") from exc


def load_article_settings(dal=None) -> ArticleAcquisitionSettings:
    return parse_article_settings(read_setting(ARTICLE_SETTINGS_KEY, dal))


def article_settings_view(raw: str | None) -> dict:
    view = {"values": None, "defaults": ArticleAcquisitionSettings().model_dump(),
            "setting_source": "profile" if raw is not None else "default", "error_code": None}
    try:
        view["values"] = parse_article_settings(raw).model_dump()
    except DataSourcePolicyFailure as exc:
        view["error_code"] = exc.code
    return view
