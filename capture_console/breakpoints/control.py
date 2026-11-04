"""Versioned allow-list dispatch shared by the API and worker control channel."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import Issue, Patch, RuleInput
from .validation import identifier


class Empty(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class RuleCommand(Empty):
    id: str
    expected_revision: int = Field(ge=0)
    rule: RuleInput


class Page(Empty):
    cursor: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=50)


class Selected(Empty):
    id: str


class Resolve(Selected):
    operation_id: str
    expected_revision: int = Field(ge=1)
    action: Literal['apply', 'original', 'abort']
    patch: Patch | None = None


SCHEMAS = {'status': Empty, 'rule': RuleCommand, 'enable': Empty, 'disable': Empty,
           'heartbeat': Empty, 'pending': Page, 'detail': Selected, 'resolve': Resolve,
           'release-all': Empty, 'stop': Empty}


def validate(command, payload):
    try:
        schema = SCHEMAS[command]
        parsed = schema.model_validate(payload)
        for field in ('id', 'operation_id'):
            if hasattr(parsed, field):
                identifier(getattr(parsed, field))
        return parsed
    except (KeyError, TypeError, ValueError, ValidationError):
        # Do not return pydantic errors: they echo supplied secrets and full bodies.
        raise Issue('invalid_command', 422) from None


def dispatch(engine, command, payload):
    value = validate(command, payload)
    engine.tick()
    if command == 'status':
        return engine.status()
    if command == 'rule':
        return engine.put_rule(value.id, value.expected_revision, value.rule)
    if command == 'enable':
        return engine.enable()
    if command == 'heartbeat':
        return engine.heartbeat()
    if command in {'disable', 'release-all'}:
        return engine.release_all()
    if command == 'pending':
        return engine.pending(value.cursor, value.limit)
    if command == 'detail':
        return engine.detail(value.id)
    if command == 'resolve':
        return engine.resolve(value.id, value.operation_id, value.expected_revision, value.action, value.patch)
    if command == 'stop':
        return engine.stop()
    raise Issue('invalid_command', 422)


def error_json(issue):
    return {'code': issue.code, 'status': issue.status, 'title': '断点操作未完成',
            'message': '当前操作未生效，请检查连接和断点状态。', 'recovery_action': '刷新断点状态'}
