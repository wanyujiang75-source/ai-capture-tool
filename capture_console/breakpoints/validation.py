"""Validate edits without touching a live connection or decoding unbounded bodies."""

import base64
from dataclasses import replace
import ipaddress
import json
import re
from urllib.parse import urlsplit, unquote_to_bytes

from .models import BODY_LIMIT, HEADER_LIMIT, METHODS, Issue

MANAGED = {'host', 'content-length', 'transfer-encoding', 'content-encoding',
           'connection', 'trailer', 'te', 'upgrade', 'proxy-authorization', 'proxy-authenticate'}
INTEGRITY = {'etag', 'content-md5', 'digest', 'content-digest', 'repr-digest'}
TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
IDENTIFIER = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise Issue('invalid_identifier', 422)
    return value


def host(value):
    try:
        value = value.rstrip('.').lower()
        try:
            return ipaddress.ip_address(value).compressed
        except ValueError:
            value = value.encode('idna').decode('ascii')
        if len(value) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p)
                                   for p in value.split('.')):
            raise ValueError()
        return value
    except (UnicodeError, ValueError):
        raise Issue('invalid_origin', 422) from None


def url(value):
    try:
        if len(value.encode('utf-8')) > 8192 or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
            raise ValueError()
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None or parsed.fragment:
            raise ValueError()
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
        if not 1 <= port <= 65535:
            raise ValueError()
        return (parsed.scheme, host(parsed.hostname), port), parsed.path or '/'
    except (ValueError, UnicodeError):
        raise Issue('invalid_url', 422) from None


def headers_size(headers):
    if len(headers) > 200:
        raise Issue('headers_too_large', 422)
    size = 0
    for name, value in headers:
        if not TOKEN.fullmatch(name) or any(ord(c) < 32 and c != '\t' or ord(c) == 127 for c in value):
            raise Issue('invalid_header', 422)
        size += len(name.encode('utf-8')) + len(value.encode('utf-8')) + 4
    if size > HEADER_LIMIT:
        raise Issue('headers_too_large', 422)
    return size


def metadata_size(message):
    url(message.url)
    if message.method not in METHODS or (message.status is not None and not 200 <= message.status <= 599):
        raise Issue('unsupported_message', 422)
    return headers_size(message.headers) + len(message.url.encode('utf-8'))


def rule_key(rule):
    if rule.method not in METHODS or not rule.path.startswith('/') or any(c in rule.path for c in '?\r\n#'):
        raise Issue('invalid_rule', 422)
    if len(rule.path.encode('utf-8')) > 8192:
        raise Issue('invalid_rule', 422)
    return rule.scheme, host(rule.host), rule.port or (443 if rule.scheme == 'https' else 80)


def edited(original, patch, stage, request_method):
    if stage == 'request' and patch.status is not None or stage == 'response' and (patch.url is not None or patch.method is not None):
        raise Issue('invalid_stage_patch', 422)
    target = patch.url if patch.url is not None else original.url
    if url(target)[0] != url(original.url)[0]:
        raise Issue('cross_origin_edit', 422)
    method = patch.method if patch.method is not None else original.method
    if method not in METHODS:
        raise Issue('invalid_method', 422)
    status = patch.status if patch.status is not None else original.status
    no_body = method == 'HEAD' if stage == 'request' else request_method == 'HEAD' or status in {204, 304}
    headers = tuple(patch.headers) if patch.headers is not None else original.headers
    headers_size(headers)
    managed = lambda fields: [(k.lower(), v) for k, v in fields if k.lower() in MANAGED]
    if managed(headers) != managed(original.headers):
        raise Issue('managed_header', 422)
    body = original.body
    if patch.body_text is not None:
        if not original.editable_body:
            raise Issue('body_not_editable', 422)
        try:
            body = patch.body_text.encode('utf-8')
        except UnicodeError:
            raise Issue('invalid_text', 422) from None
        if len(body) > BODY_LIMIT:
            raise Issue('body_too_large', 422)
        content_type = next((v.lower().split(';')[0].strip() for k, v in headers if k.lower() == 'content-type'), 'text/plain')
        if no_body and not body:
            pass
        elif content_type == 'application/json' or content_type.endswith('+json'):
            try:
                json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, RecursionError):
                raise Issue('invalid_json', 422) from None
        elif content_type == 'application/x-www-form-urlencoded':
            try:
                if re.search(r'%(?![0-9a-fA-F]{2})', patch.body_text):
                    raise ValueError()
                unquote_to_bytes(body).decode('utf-8')
            except (ValueError, UnicodeError):
                raise Issue('invalid_form', 422) from None
        elif not content_type.startswith('text/'):
            raise Issue('body_not_editable', 422)
    if no_body and body:
        raise Issue('body_forbidden', 422)
    if not original.editable_body and (method != original.method or status != original.status):
        raise Issue('restricted_semantics', 422)
    if body != original.body:
        headers = tuple((k, v) for k, v in headers if k.lower() not in INTEGRITY | {'content-length'})
    else:
        body = original.body
    return replace(original, url=target, method=method, status=status, headers=headers, body=body)


def message_json(message):
    return {'url': message.url, 'method': message.method, 'status': message.status,
            'headers': [list(pair) for pair in message.headers],
            'body_base64': base64.b64encode(message.body).decode('ascii'),
            'editable_body': message.editable_body, 'protocol': message.protocol}
