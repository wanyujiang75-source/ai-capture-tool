"""Bounded control schemas and immutable messages, independent of proxy internals."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BODY_LIMIT = 256 * 1024
HEADER_LIMIT = 64 * 1024
FRAME_LIMIT = 1024 * 1024
METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'}


class Issue(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


class RuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    scheme: Literal['http', 'https']
    host: str = Field(min_length=1, max_length=253)
    port: int | None = Field(default=None, ge=1, le=65535)
    path: str = Field(min_length=1, max_length=8192)
    path_match: Literal['exact', 'prefix'] = 'exact'
    method: str = 'GET'
    stage: Literal['request', 'response', 'both'] = 'request'
    once: bool = True
    enabled: bool = True
    timeout_seconds: Literal[15, 30, 60] = 30


class Patch(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    url: str | None = Field(default=None, max_length=8192)
    method: str | None = Field(default=None, max_length=16)
    status: int | None = Field(default=None, strict=True, ge=200, le=599)
    headers: list[tuple[str, str]] | None = Field(default=None, max_length=200)
    body_text: str | None = Field(default=None, max_length=BODY_LIMIT)


@dataclass(frozen=True)
class Message:
    url: str
    method: str = 'GET'
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b''
    status: int | None = None
    protocol: str = 'http/1.1'
    streaming: bool = False
    editable_body: bool = True


@dataclass(frozen=True)
class Admission:
    flow_id: str
    pending_id: str | None


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    original: Message | None
    effective: Message | None
