"""Bounded, metadata-only evidence from the current single-app capture path."""

import math
import time


class ApplicationNetworkEvidence:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.last_response = self.last_failure = self.last_status = None
        self.responses = 0

    def response(self, status):
        if type(status) is not int or not 200 <= status <= 599:
            return
        self.last_response, self.last_status = self.clock(), status
        self.responses += 1

    def failure(self):
        self.last_failure = self.clock()

    def summary(self):
        now = self.clock()
        age = None if self.last_response is None else max(0, now - self.last_response)
        recent_response = age is not None and age <= 30
        recent_failure = self.last_failure is not None and 0 <= now - self.last_failure <= 30
        if recent_failure:
            state = 'partial' if recent_response else 'connection_failed'
        elif recent_response:
            state = 'server_error' if self.last_status >= 400 else 'responded'
        else:
            state = 'waiting' if age is None else 'quiet'
        return {'state': state, 'https_response_count': self.responses, 'last_status_code': self.last_status,
                'response_age_seconds': age, 'observed_at': now}


def current_evidence(value, *, now):
    if isinstance(value, dict):
        observed = value.get('observed_at')
        if type(observed) in (int, float) and math.isfinite(observed) and 0 <= now - observed <= 15:
            age = value.get('response_age_seconds')
            if value.get('state') in {'responded', 'partial', 'server_error'} and (
                    type(age) not in (int, float) or not math.isfinite(age) or age < 0 or age + now - observed > 30):
                return {'state': 'unverified'}
            return {key: value.get(key) for key in (
                'state', 'https_response_count', 'last_status_code', 'response_age_seconds')}
    return {'state': 'unverified'}
