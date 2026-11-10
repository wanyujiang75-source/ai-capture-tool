import importlib
import importlib.util
import unittest
from dataclasses import replace


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        module = "capture_console.android_capture_admission"
        self.assertIsNotNone(importlib.util.find_spec(module), "NR-0 contract is missing")
        self.api = importlib.import_module(module)
        self.now = 100.0
        self.gate = self.api.AdmissionGate(clock=lambda: self.now)
        self.identity = self.api.CaptureIdentity(
            serial="phone", android_user="0", package="com.example.app", version_code="98",
            signers=("a" * 64,), signing_lineage=(),
            apks=(("base.apk", "b" * 64), ("split_config.arm64_v8a.apk", "c" * 64)),
            system_fingerprint="vendor/product/build", engine_version="trial-1",
            route="trusted_proxy", connection_epoch="adb-1",
            endpoint_sha256="d" * 64, vpn_epoch="vpn-1",
        )
        self.candidate = self.api.Candidate(
            route="trusted_proxy", mechanism_id="isolated-fixture-1",
            mechanism_verified=True, authorized=True, bounded=True,
        )
        self.inspection = {
            "serial": "phone", "device_kind": "physical", "status": "blocked",
            "device": {"boot": "1", "user": "0"},
            "package_identity": {
                "package_name": "com.example.app", "version_code": "98",
                "debuggable": False, "provenance": "unverified",
                "apk_paths": ["/data/app/app/base.apk", "/data/app/app/split_config.arm64_v8a.apk"],
            },
            "issues": ["no_verified_capture_path"],
            "vpn_state": "transport_observed",
        }

    def check(self, gate=None, **changes):
        args = {"identity": self.identity, "candidate": self.candidate}
        args.update(changes)
        return (gate or self.gate).check(self.inspection, **args)

    def verified(self):
        self.check()
        probe_id = self.gate.begin_probe()
        self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True)
        return self.gate.stop(cleanup_confirmed=True)

    def test_new_nondebuggable_device_can_probe_without_past_business_evidence(self):
        self.assertEqual(self.check(), self.api.Decision("probe_available"))
        self.assertFalse(self.gate.decision.can_record)

    def test_missing_candidate_does_not_confuse_adb_with_capture(self):
        self.assertEqual(self.check(candidate=None), self.api.Decision("blocked", "candidate_missing"))
        with self.assertRaises(ValueError):
            self.gate.begin_probe()

    def test_candidate_requires_mechanism_authority_budget_and_matching_route(self):
        for changes in ({"authorized": False}, {"mechanism_verified": False}, {"bounded": False}, {"route": "tls_keylog"}):
            with self.subTest(changes=changes):
                self.assertFalse(self.check(candidate=replace(self.candidate, **changes)).can_probe)

    def test_ap0_unknown_disconnect_unauthorized_and_wrong_device_do_not_probe(self):
        for status in ("unknown", "disconnected", "offline", "unauthorized", "ambiguous_device", "wrong_device_kind"):
            with self.subTest(status=status):
                self.inspection["status"] = status
                self.assertFalse(self.check().can_probe)

    def test_missing_identity_and_ap0_fields_fail_closed(self):
        self.assertFalse(self.check(identity=None).can_probe)
        for key in tuple(self.inspection):
            with self.subTest(key=key):
                value = self.inspection.pop(key)
                self.assertFalse(self.check().can_probe)
                self.inspection[key] = value

    def test_unknown_or_lost_vpn_cannot_be_admitted(self):
        for state in ("unknown", None, "disconnected"):
            with self.subTest(state=state):
                self.inspection["vpn_state"] = state
                self.assertEqual(self.check(), self.api.Decision("needs_action", "vpn_not_confirmed"))

    def test_target_user_boot_package_and_split_must_match(self):
        for key, value in (("serial", "other"), ("device_kind", "emulator"), ("device", {"boot": "0", "user": "0"}), ("device", {"boot": "1", "user": "10"}), ("package_identity", {})):
            with self.subTest(key=key, value=value):
                original = self.inspection[key]
                self.inspection[key] = value
                self.assertFalse(self.check().can_probe)
                self.inspection[key] = original
        self.inspection["package_identity"]["apk_paths"] = ["/data/app/app/base.apk"]
        self.assertFalse(self.check().can_probe)

    def test_ap0_failure_details_are_not_exposed(self):
        self.inspection["issues"].append("package_unavailable secret-token")
        self.assertEqual(self.check(), self.api.Decision("blocked", "inspection_incomplete"))
        self.assertNotIn("secret", repr(self.gate.decision))

    def test_busy_and_unrecovered_resources_block(self):
        self.assertFalse(self.check(busy=True).can_probe)
        self.assertEqual(self.check(recovery_required=True), self.api.Decision("recovery_required", "cleanup_unconfirmed"))
        self.assertFalse(self.check().can_probe)
        self.gate.stop(cleanup_confirmed=True)
        self.assertTrue(self.check().can_probe)

    def test_success_requires_current_probe_business_evidence_then_cleanup(self):
        self.check()
        probe_id = self.gate.begin_probe()
        self.assertEqual(self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True), self.api.Decision("stopping", "evidence_received"))
        self.assertFalse(self.gate.decision.can_record)
        self.assertEqual(self.gate.stop(cleanup_confirmed=True), self.api.Decision("verified"))

    def test_partial_body_or_unrelated_http_never_verifies(self):
        for field in ("request_complete", "response_complete", "business_correlated"):
            self.gate = self.api.AdmissionGate(clock=lambda: self.now)
            self.check()
            probe_id = self.gate.begin_probe()
            result = dict(request_complete=True, response_complete=True, business_correlated=True)
            result[field] = False
            self.assertEqual(self.gate.observe(probe_id, **result).state, "probing")
            self.assertFalse(self.gate.stop(cleanup_confirmed=True).can_record)

    def test_no_recording_before_proof_and_fresh_snapshot(self):
        self.check()
        with self.assertRaises(ValueError):
            self.gate.start_recording(self.inspection, identity=self.identity, candidate=self.candidate)
        self.verified()
        self.inspection["status"] = "disconnected"
        with self.assertRaises(ValueError):
            self.gate.start_recording(self.inspection, identity=self.identity, candidate=self.candidate)

    def test_all_identity_fields_invalidate_same_version_evidence(self):
        changes = {
            "serial": "other", "android_user": "10", "package": "com.other.app", "version_code": "99",
            "signers": ("e" * 64,), "signing_lineage": ("f" * 64,),
            "apks": (("base.apk", "e" * 64), ("split_config.arm64_v8a.apk", "c" * 64)),
            "system_fingerprint": "vendor/new/build", "engine_version": "trial-2",
            "route": "tls_keylog", "connection_epoch": "adb-2", "endpoint_sha256": "e" * 64,
            "vpn_epoch": "vpn-2",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                self.gate = self.api.AdmissionGate(clock=lambda: self.now)
                self.verified()
                self.assertFalse(self.check(identity=replace(self.identity, **{field: value})).can_record)

    def test_changed_candidate_does_not_reuse_proof(self):
        self.verified()
        self.assertFalse(self.check(candidate=replace(self.candidate, mechanism_id="different")).can_record)

    def test_expiry_uses_observation_time_not_cleanup_time(self):
        self.check()
        probe_id = self.gate.begin_probe()
        self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True)
        self.now += 590
        self.gate.stop(cleanup_confirmed=True)
        self.assertTrue(self.check().can_record)
        self.now += 10
        self.assertEqual(self.check(), self.api.Decision("probe_available"))

    def test_expiry_does_not_interrupt_recording_but_stop_requires_new_check(self):
        self.verified()
        self.gate.start_recording(self.inspection, identity=self.identity, candidate=self.candidate)
        self.now += 601
        self.assertEqual(self.check(), self.api.Decision("recording"))
        self.gate.stop(cleanup_confirmed=True)
        self.assertFalse(self.gate.decision.can_record)
        self.assertEqual(self.check(), self.api.Decision("probe_available"))

    def test_active_identity_change_requires_cleanup_and_new_probe(self):
        self.verified()
        self.gate.start_recording(self.inspection, identity=self.identity, candidate=self.candidate)
        self.assertEqual(self.check(identity=replace(self.identity, connection_epoch="adb-2")).state, "stopping")
        self.assertFalse(self.check().can_probe)
        self.gate.stop(cleanup_confirmed=True)
        self.assertEqual(self.check(), self.api.Decision("probe_available"))

    def test_old_probe_or_other_backend_instance_cannot_accept_evidence(self):
        self.check()
        old_id = self.gate.begin_probe()
        other = self.api.AdmissionGate(clock=lambda: self.now)
        self.assertEqual(self.check(other).state, "probe_available")
        new_id = other.begin_probe()
        self.assertNotEqual(old_id, new_id)
        with self.assertRaises(ValueError):
            other.observe(old_id, request_complete=True, response_complete=True, business_correlated=True)
        self.assertEqual(other.decision.state, "probing")

    def test_failed_cleanup_cannot_leave_verified_evidence(self):
        self.verified()
        self.assertEqual(self.gate.stop(cleanup_confirmed=False), self.api.Decision("recovery_required", "cleanup_unconfirmed"))
        self.assertFalse(self.check().can_record)
        self.gate.stop(cleanup_confirmed=True)
        self.assertEqual(self.check(), self.api.Decision("probe_available"))

    def test_cancel_invalidates_probe_and_stop_is_idempotent(self):
        self.check()
        probe_id = self.gate.begin_probe()
        self.gate.cancel()
        with self.assertRaises(ValueError):
            self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True)
        self.assertEqual(self.gate.stop(cleanup_confirmed=True), self.api.Decision("stopped"))
        self.assertEqual(self.gate.stop(cleanup_confirmed=True), self.api.Decision("stopped"))
        self.assertFalse(self.gate.decision.can_record)

    def test_probe_timeout_and_transaction_budget_never_create_proof(self):
        self.check()
        probe_id = self.gate.begin_probe()
        self.now += 120
        self.assertEqual(self.gate.decision, self.api.Decision("stopping", "probe_timeout"))
        with self.assertRaises(ValueError):
            self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True)
        self.gate.stop(cleanup_confirmed=True)
        self.check()
        probe_id = self.gate.begin_probe()
        for _ in range(20):
            self.gate.observe(probe_id, request_complete=False, response_complete=False, business_correlated=False)
        self.assertEqual(self.gate.decision, self.api.Decision("stopping", "probe_budget_exhausted"))
        self.assertFalse(self.gate.stop(cleanup_confirmed=True).can_record)

    def test_runtime_failure_invalidates_proof(self):
        self.verified()
        self.gate.start_recording(self.inspection, identity=self.identity, candidate=self.candidate)
        self.assertEqual(self.gate.report_failure(), self.api.Decision("stopping", "capture_path_failed"))
        self.gate.stop(cleanup_confirmed=True)
        self.assertEqual(self.check(), self.api.Decision("probe_available"))

    def test_invalid_or_backward_clock_fails_closed(self):
        for value in (float("nan"), float("inf"), 99.0):
            with self.subTest(value=value):
                self.now = 100.0
                self.gate = self.api.AdmissionGate(clock=lambda: self.now)
                self.verified()
                self.now = value
                self.assertFalse(self.gate.decision.can_record)

    def test_identity_rejects_unbounded_or_incomplete_values(self):
        for changes in ({"serial": "phone;id"}, {"package": "com.app;id"}, {"android_user": "-1"}, {"version_code": ""}, {"signers": ()}, {"signers": ("bad",)}, {"apks": ()}, {"apks": (("split.apk", "b" * 64),)}, {"apks": (("base.apk", "b" * 64), ("base.apk", "c" * 64))}, {"endpoint_sha256": "http://user:secret@host"}, {"connection_epoch": ""}, {"engine_version": "x" * 1000}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(self.identity, **changes)

    def test_identity_set_order_is_canonical(self):
        equivalent = replace(self.identity, apks=tuple(reversed(self.identity.apks)))
        self.assertEqual(self.identity, equivalent)

    def test_repeated_cleanup_confirmation_preserves_verified_decision(self):
        self.verified()
        self.assertEqual(self.gate.stop(cleanup_confirmed=True), self.api.Decision("verified"))
        self.now += 600
        self.assertFalse(self.gate.decision.can_record)

    def test_clock_failure_cannot_clear_required_recovery(self):
        self.check(recovery_required=True)
        self.now = float("nan")
        self.assertEqual(self.gate.decision.state, "recovery_required")
        self.now = 101.0
        self.assertEqual(self.check().state, "recovery_required")

    def test_changed_snapshot_during_cleanup_discards_pending_proof(self):
        for field, value in (("serial", "other"), ("status", "disconnected")):
            with self.subTest(field=field):
                self.gate = self.api.AdmissionGate(clock=lambda: self.now)
                self.check()
                probe_id = self.gate.begin_probe()
                self.gate.observe(probe_id, request_complete=True, response_complete=True, business_correlated=True)
                original = self.inspection[field]
                try:
                    self.inspection[field] = value
                    self.check()
                    self.assertFalse(self.gate.stop(cleanup_confirmed=True).can_record)
                finally:
                    self.inspection[field] = original

    def test_malformed_nested_ap0_values_are_not_admitted_or_echoed(self):
        for key in ("device", "package_identity"):
            for value in ("secret-token", ["secret-token"], 10):
                with self.subTest(key=key, value=value):
                    old = self.inspection[key]
                    try:
                        self.inspection[key] = value
                        decision = self.check()
                        self.assertFalse(decision.can_probe)
                        self.assertNotIn("secret", repr(decision))
                    finally:
                        self.inspection[key] = old


if __name__ == "__main__":
    unittest.main()
