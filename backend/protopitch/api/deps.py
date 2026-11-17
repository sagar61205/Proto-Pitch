from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from protopitch.auth import Principal, require_principal
from protopitch.context import AppContext
from protopitch.db.session import session_scope


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx


def get_session(request: Request) -> Iterator[Session]:
    with session_scope(get_ctx(request).sessions) as session:
        yield session


Ctx = Annotated[AppContext, Depends(get_ctx)]
Db = Annotated[Session, Depends(get_session)]
Actor = Annotated[Principal, Depends(require_principal)]
