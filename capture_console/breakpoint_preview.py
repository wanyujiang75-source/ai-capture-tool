"""Read-only bounded previews of content-addressed breakpoint versions."""

import copy
import hashlib
import os
import re
import stat
import zlib


def preview_versions(root, stages):
    result = copy.deepcopy(stages)
    for stage in ('request', 'response'):
        for label in ('original', 'effective'):
            value = result.get(stage, {}).get(label)
            if not isinstance(value, dict):
                continue
            value.update(body_text='', body_available=False, body_truncated=False)
            name = value.get('body_file', '')
            if not isinstance(name, str) or not re.fullmatch(r'[0-9a-f]{64}\.bp\.bin', name):
                continue
            try:
                fd = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > 262144:
                        continue
                    data = stream.read(262145)
                if len(data) != value.get('body_size') or hashlib.sha256(data).hexdigest() != name[:64]:
                    continue
                headers = {str(k).lower(): str(v).lower() for k, v in value.get('headers', [])}
                encoding = headers.get('content-encoding', 'identity')
                if encoding in {'gzip', 'deflate'}:
                    decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
                    data = decoder.decompress(data, 32769)
                    value['body_truncated'] = not decoder.eof
                elif encoding not in {'', 'identity'}:
                    continue
                value['body_truncated'] |= len(data) > 32768
                value['body_text'] = data[:32768].decode('utf-8', 'replace').encode()[:32768].decode('utf-8', 'ignore')
                value['body_available'] = True
            except (OSError, ValueError, TypeError, zlib.error):
                pass
    return result
