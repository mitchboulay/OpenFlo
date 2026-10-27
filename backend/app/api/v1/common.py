"""Dependencies shared by the ``/api/v1`` routers."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request

from ...config import Settings
from ...persistence.repository import Repository
from ...repositories._rows import DEFAULT_LIMIT, MAX_LIMIT


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


RepoDep = Annotated[Repository, Depends(get_repo)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
# Every list: limit default 50, max 500, newest first, with a before_id cursor (Performance NFR).
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Page size")]

__all__ = ["DEFAULT_LIMIT", "Limit", "RepoDep", "SettingsDep"]
