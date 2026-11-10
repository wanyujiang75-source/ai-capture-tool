"""Process-local admission contracts, not a collector or an API authorization layer.

Only trusted adapters may attest business completeness. This module performs no I/O;
it neither discovers a working decryption path nor changes device/network state.
"""

import math
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath


_ROUTES = {"trusted_proxy", "tls_keylog", "app_diagnostics", "server_logs"}


@dataclass(frozen=True, kw_only=True)
class CaptureIdentity:
    """Immutable, bounded evidence supplied by an identity collector, not provenance proof."""

    serial: str
    android_user: str
    package: str
    version_code: str
    signers: tuple[str, ...]
    signing_lineage: tuple[str, ...]
    apks: tuple[tuple[str, str], ...]
    system_fingerprint: str
    engine_version: str
    route: str
    connection_epoch: str
    endpoint_sha256: str
    vpn_epoch: str

    def __post_init__(self):
        patterns = {
            "serial": r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",
            "android_user": r"[0-9]{1,10}", "version_code": r"[0-9]{1,20}",
            "package": r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+",
        }
        for name, pattern in patterns.items():
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > 255 or not re.fullmatch(pattern, value):
                raise ValueError("invalid_capture_identity")
        for value in (self.system_fingerprint, self.engine_version, self.connection_epoch, self.vpn_epoch):
            if not isinstance(value, str) or not re.fullmatch(r"[!-~]{1,512}", value):
                raise ValueError("invalid_capture_identity")
        if len(self.engine_version) > 128 or self.route not in _ROUTES:
            raise ValueError("invalid_capture_identity")
        hashes = (self.signers, self.signing_lineage)
        if not self.signers or any(not isinstance(items, tuple) or len(items) > 32 for items in hashes):
            raise ValueError("invalid_capture_identity")
        for items in (*hashes, (self.endpoint_sha256,)):
            if any(not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{64}", item) for item in items):
                raise ValueError("invalid_capture_identity")
            if len(set(items)) != len(items):
                raise ValueError("invalid_capture_identity")
        if not isinstance(self.apks, tuple) or not 1 <= len(self.apks) <= 128:
            raise ValueError("invalid_capture_identity")
        for item in self.apks:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("invalid_capture_identity")
            name, digest = item
            if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}\.apk", name)
                    or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                raise ValueError("invalid_capture_identity")
        names = [name for name, _ in self.apks]
        if "base.apk" not in names or len(names) != len(set(names)):
            raise ValueError("invalid_capture_identity")
        object.__setattr__(self, "apks", tuple(sorted(self.apks)))
        object.__setattr__(self, "signers", tuple(sorted(self.signers)))


@dataclass(frozen=True, kw_only=True)
class Candidate:
    """Attested route prerequisites; ADB connectivity alone cannot create a candidate."""

    route: str
    mechanism_id: str
    mechanism_verified: bool = False
    authorized: bool = False
    bounded: bool = False

    def __post_init__(self):
        if (self.route not in _ROUTES or not isinstance(self.mechanism_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", self.mechanism_id)
                or any(type(value) is not bool for value in (self.mechanism_verified, self.authorized, self.bounded))):
            raise ValueError("invalid_candidate")


@dataclass(frozen=True)
class Decision:
    """Safe reason codes only; never retain command output, private config, or credentials."""

    state: str
    reason: str = ""

    @property
    def can_probe(self):
        return self.state == "probe_available"

    @property
    def can_record(self):
        return self.state == "verified"


def _eligibility(inspection, identity, candidate, busy):
    if not isinstance(identity, CaptureIdentity):
        return Decision("blocked", "identity_incomplete")
    if not isinstance(inspection, dict):
        return Decision("needs_action", "inspection_incomplete")
    if inspection.get("status") != "blocked":
        return Decision("needs_action", "device_not_confirmed")
    if inspection.get("vpn_state") != "transport_observed":
        return Decision("needs_action", "vpn_not_confirmed")
    device = inspection.get("device") or {}
    package = inspection.get("package_identity") or {}
    if not isinstance(device, dict) or not isinstance(package, dict):
        return Decision("blocked", "inspection_incomplete")
    issues = inspection.get("issues")
    if (not isinstance(issues, (list, tuple)) or len(issues) > 32
            or any(issue != "no_verified_capture_path" for issue in issues)):
        return Decision("blocked", "inspection_incomplete")
    if (inspection.get("serial") != identity.serial or inspection.get("device_kind") != "physical"
            or device.get("user") != identity.android_user or device.get("boot") != "1"
            or package.get("package_name") != identity.package or package.get("version_code") != identity.version_code):
        return Decision("needs_action", "target_not_confirmed")
    paths = package.get("apk_paths")
    if (not isinstance(paths, list) or len(paths) > 128 or not paths
            or any(not isinstance(path, str) or len(path) > 4096 or not path.startswith("/") for path in paths)
            or sorted(PurePosixPath(path).name for path in paths) != [name for name, _ in identity.apks]):
        return Decision("blocked", "apk_inventory_mismatch")
    if not isinstance(candidate, Candidate):
        return Decision("blocked", "candidate_missing")
    if (candidate.route != identity.route or not candidate.mechanism_verified
            or not candidate.authorized or not candidate.bounded):
        return Decision("blocked", "candidate_not_admitted")
    if busy:
        return Decision("needs_action", "device_busy")
    return None


class AdmissionGate:
    """Single-owner state model. Callers must serialize events and perform actual cleanup.

    Each instance has fresh probe IDs and no persisted proof. A trusted runtime must
    supply fresh snapshots and poll decisions for deadlines; no timers are started.
    """

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._last_time = None
        self._decision = Decision("idle")
        self._context = None
        self._proof = None
        self._pending_proof = None
        self._probe_id = None
        self._deadline = None
        self._transactions = 0

    def _halt(self, reason):
        self._proof = self._pending_proof = None
        self._probe_id = None
        self._deadline = None
        self._decision = Decision("stopping", reason)

    def _tick(self):
        now = self._clock()
        if not isinstance(now, (int, float)) or not math.isfinite(now) or (self._last_time is not None and now < self._last_time):
            if self._decision.state == "recovery_required":
                return None
            if self._decision.state in ("probing", "recording", "stopping"):
                self._halt("clock_invalid")
            else:
                self._proof = self._pending_proof = None
                self._decision = Decision("needs_action", "clock_invalid")
            return None
        self._last_time = now
        if self._decision.state == "probing" and now >= self._deadline:
            self._halt("probe_timeout")
        if self._decision.state == "verified" and (not self._proof or now - self._proof[1] >= 600):
            self._proof = None
            self._decision = Decision("probe_available")
        return now

    @property
    def decision(self):
        self._tick()
        return self._decision

    def check(self, inspection, *, identity, candidate, recovery_required=False, busy=False):
        now = self._tick()
        if recovery_required:
            self._proof = self._pending_proof = None
            self._probe_id = self._deadline = None
            self._decision = Decision("recovery_required", "cleanup_unconfirmed")
        if self._decision.state == "stopping" and self._pending_proof:
            if _eligibility(inspection, identity, candidate, busy) or self._context != (identity, candidate):
                self._halt("capture_conditions_changed")
        if self._decision.state in ("stopping", "recovery_required") or now is None:
            return self._decision
        failure = _eligibility(inspection, identity, candidate, busy)
        context = (identity, candidate)
        if self._decision.state in ("probing", "recording"):
            if failure or self._context != context:
                self._halt("capture_conditions_changed")
            return self._decision
        if failure:
            self._proof = None
            self._context = None
            self._decision = failure
        else:
            self._context = context
            if self._proof and self._proof[0] == context and now - self._proof[1] < 600:
                self._decision = Decision("verified")
            else:
                self._proof = None
                self._decision = Decision("probe_available")
        return self._decision

    def begin_probe(self):
        if not self.decision.can_probe:
            raise ValueError("probe_not_admitted")
        self._proof = self._pending_proof = None
        self._probe_id = uuid.uuid4().hex
        self._deadline = self._last_time + 120
        self._transactions = 0
        self._decision = Decision("probing")
        return self._probe_id

    def observe(self, probe_id, *, request_complete, response_complete, business_correlated):
        if self.decision.state != "probing" or probe_id != self._probe_id:
            raise ValueError("probe_not_current")
        self._transactions += 1
        if all(value is True for value in (request_complete, response_complete, business_correlated)):
            self._pending_proof = (self._context, self._last_time)
            self._probe_id = self._deadline = None
            self._decision = Decision("stopping", "evidence_received")
        elif self._transactions >= 20:
            self._halt("probe_budget_exhausted")
        return self._decision

    def start_recording(self, inspection, *, identity, candidate, **conditions):
        if not self.check(inspection, identity=identity, candidate=candidate, **conditions).can_record:
            raise ValueError("recording_not_admitted")
        self._decision = Decision("recording")
        return self._decision

    def report_failure(self):
        self._halt("capture_path_failed")
        return self._decision

    def cancel(self):
        self._halt("cancelled")
        return self._decision

    def stop(self, *, cleanup_confirmed):
        now = self._tick()
        if self._decision.state == "verified" and cleanup_confirmed is True:
            return self._decision
        pending = self._pending_proof
        self._proof = self._pending_proof = None
        self._probe_id = self._deadline = None
        if cleanup_confirmed is not True:
            self._decision = Decision("recovery_required", "cleanup_unconfirmed")
        elif pending and now is not None and now - pending[1] < 600:
            self._proof = pending
            self._decision = Decision("verified")
        else:
            self._decision = Decision("stopped")
        return self._decision
