"""Bounded acceptance probe for the installed codecs, not a product decoder."""

import brotli
import zlib


LIMIT = 256 * 1024


def editable(message):
    data = message.raw_content or b''
    if len(data) > LIMIT:
        return False
    encoding = message.headers.get('content-encoding', '').lower()
    try:
        if encoding in {'gzip', 'deflate'}:
            decoder = zlib.decompressobj(31 if encoding == 'gzip' else 15)
            data = decoder.decompress(data, LIMIT + 1)
            if not decoder.eof or decoder.unused_data:
                return False
        elif encoding == 'br':
            decoder = brotli.Decompressor()
            # Brotli 1.2.0 may overshoot this buffer threshold; never accept that output.
            data = decoder.process(data, output_buffer_limit=LIMIT + 1)
            if not decoder.is_finished():
                return False
        elif encoding not in {'', 'identity'}:
            return False
        if len(data) > LIMIT:
            return False
        data.decode('utf-8')
        return True
    except (ValueError, zlib.error, brotli.error):
        return False
