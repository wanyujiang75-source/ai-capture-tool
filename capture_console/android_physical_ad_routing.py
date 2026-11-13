"""Bounded, payload-free connection diagnostics for physical-device routing."""

import ipaddress
import re

# Confirmed target-UID dependencies in AD-1; never learn bypasses from TLS failures.
STICKER_AD_DOMAINS = ('doubleclick.net', 'googlesyndication.com', 'googleadservices.com', '2mdn.net')
STICKER_AD_HOSTS = frozenset({
    'googleads.g.doubleclick.net', 'pagead2.googlesyndication.com',
    'lh3.googleadsserving.cn', 'static.googleadsserving.cn',
    'pagead2.googleadservices.com', 'fundingchoicesmessages.google.com',
    'www.googletagservices.com', 'tpc.googlesyndication.com',
    # Shared font endpoints observed in the ad WebView dependency chain.
    # Their payloads are opaque for StickerHub, not classified by URL path.
    'fonts.googleapis.com', 'fonts.gstatic.com', 'www.gstatic.com',
    # Ads SDK dependency observed in the target UID's certificate-failure stack.
    # This CDN node is not globally ad-exclusive: do not broaden to *.gvt1.com.
    'rr1---sn-i3belnls.gvt1.com',
})


class RoutingDiagnostics:
    def __init__(self):
        self.entries = {}
        self.overflow = 0

    def record(self, host, role, route, failure=False):
        if not isinstance(host, str) or len(host) > 253:
            return
        host = host.lower().rstrip('.')
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host):
            return
        if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
               for label in host.split('.')):
            return
        try:
            ipaddress.ip_address(host)
            return
        except ValueError:
            pass
        if role not in ('target', 'login', 'unknown') or route not in ('capture', 'opaque', 'reject'):
            return
        key = (host, role, route)
        if key not in self.entries:
            if len(self.entries) >= 64:
                self.overflow += 1
                return
            self.entries[key] = dict(host=host, role=role, route=route, connections=0, tls_failures=0)
        entry = self.entries[key]
        entry['tls_failures' if failure else 'connections'] += 1

    def summary(self):
        return {'entries': [dict(entry) for entry in self.entries.values()], 'overflow': self.overflow}
