"""Cryptographic checks with TEMPORARY TEST KEYS only; never real user consent."""
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from comsol_workflow import approvals
from comsol_workflow.case import digest, sha256

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
if HAS_CRYPTO:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class TerminalBoundaryTests(unittest.TestCase):
    def test_keygen_refuses_pipeline_before_creating_files(self):
        with patch.object(approvals.sys.stdin, "isatty", return_value=False), patch.object(approvals.getpass, "getpass") as hidden:
            with self.assertRaisesRegex(ValueError, "TTY"):
                approvals.keygen_interactive("unused-private.pem", "unused-public.pem")
            hidden.assert_not_called()

    def test_approve_refuses_pipeline_before_requesting_secret(self):
        with patch.object(approvals.sys.stdin, "isatty", return_value=False), patch.object(approvals.getpass, "getpass") as hidden:
            with self.assertRaisesRegex(ValueError, "TTY"):
                approvals.approve_interactive({}, "solve", "unused.pem", "unused.json", "unused-public.pem")
            hidden.assert_not_called()

    def test_getpass_fallback_must_not_echo_password(self):
        with patch.object(approvals.getpass, "getpass", side_effect=approvals.getpass.GetPassWarning("fixture")):
            with self.assertRaisesRegex(ValueError, "hidden"):
                approvals._secret("TEST ONLY")


@unittest.skipUnless(HAS_CRYPTO, "Install the approval extra to exercise Ed25519 tests")
class SignedApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="signed-approval-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = Ed25519PrivateKey.generate()
        self.password = b"TEMPORARY-TEST-PASSWORD-ONLY"
        self.private_path = self.root / "test-private.pem"
        self.public_path = self.root / "test-public.pem"
        self.private_path.write_bytes(self.private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(self.password)))
        self.public_path.write_bytes(self.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.plan = {"created_at": (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),
                     "checks": {"valid": True}, "operation": "solve", "run_dir": str(self.root),
                     "approval_public_key": approvals.public_key_binding(self.public_path)}
        self.plan["content_digest"] = digest(self.plan)

    def change_plan(self, **changes):
        self.plan.pop("content_digest")
        self.plan.update(changes)
        self.plan["content_digest"] = digest(self.plan)

    def receipt(self, stage="assumptions", name=None, parent=None, **changes):
        # This signing fixture is confined to TemporaryDirectory and not a product entrypoint.
        payload = {"stage": stage, "action_scope": approvals.SCOPES[stage],
                   "content_digest": self.plan["content_digest"], "approved": True,
                   "approved_by": "SYNTHETIC TEST SIGNER — NOT A HUMAN APPROVAL",
                   "approved_at": datetime.now(timezone.utc).isoformat(),
                   "decision_evidence": "Cryptographic unittest fixture, never authorizes COMSOL",
                   "public_key_id": self.plan["approval_public_key"]["keyid"],
                   "parent_receipt_sha256": sha256(parent) if parent else None}
        payload.update(changes)
        # Use the documented wire format, not a production noninteractive signing API.
        signed_bytes = b"comsol-agent-workflow/approval/v1\0" + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        envelope = {"schema_version": 1, "algorithm": "Ed25519", "keyid": self.plan["approval_public_key"]["keyid"],
                    "payload": payload, "signature": base64.b64encode(self.private.sign(signed_bytes)).decode("ascii")}
        path = self.root / (name or stage + ".json")
        path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        return path

    def verify(self, path, stage="assumptions", parent=None):
        return approvals.verify_signed_receipt(path, stage, self.plan, self.public_path, parent_receipt=parent)

    def test_signed_assumptions_and_linked_solve_verify(self):
        assumptions = self.receipt()
        solve = self.receipt("solve", parent=assumptions)
        self.assertTrue(self.verify(assumptions)["approved"])
        verified = self.verify(solve, "solve", assumptions)
        self.assertEqual(verified["parent_receipt_sha256"], sha256(assumptions))

    def test_hand_edited_true_json_is_not_an_approval(self):
        path = self.root / "forged.json"
        path.write_text(json.dumps({"approved": True, "stage": "assumptions", "content_digest": self.plan["content_digest"]}))
        with self.assertRaisesRegex(ValueError, "signed approval envelope"):
            self.verify(path)

    def test_tampering_any_decision_content_invalidates_signature(self):
        path = self.receipt()
        envelope = json.loads(path.read_text(encoding="utf-8"))
        for field, value in [("approved_by", "IMPERSONATED"), ("decision_evidence", "changed"),
                             ("content_digest", "0"*64), ("action_scope", "solve")]:
            with self.subTest(field=field):
                changed = json.loads(json.dumps(envelope))
                changed["payload"][field] = value
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "signature verification"):
                    self.verify(path)

    def test_other_key_cannot_sign_for_pinned_anchor(self):
        path = self.receipt()
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["signature"] = base64.b64encode(Ed25519PrivateKey.generate().sign(approvals._canonical(envelope["payload"]))).decode("ascii")
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "signature verification"):
            self.verify(path)

    def test_replacing_public_key_file_invalidates_trust_binding(self):
        path = self.receipt()
        other = Ed25519PrivateKey.generate()
        self.public_path.write_bytes(other.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        with self.assertRaisesRegex(ValueError, "pinned"):
            self.verify(path)

    def test_user_side_copy_of_same_public_key_has_same_trust_identity(self):
        receipt = self.receipt()
        public_copy = self.root / "operator-workstation-public.pem"
        public_copy.write_bytes(self.public_path.read_bytes())
        verified = approvals.verify_signed_receipt(receipt, "assumptions", self.plan, public_copy)
        self.assertEqual(verified["public_key_id"], self.plan["approval_public_key"]["keyid"])

    def test_signature_cannot_be_replayed_for_another_plan_or_stage(self):
        path = self.receipt()
        with self.assertRaisesRegex(ValueError, "plan, stage or action"):
            self.verify(path, "solve", path)
        self.change_plan(run_dir=str(self.root / "another-run"))
        with self.assertRaisesRegex(ValueError, "plan, stage or action"):
            self.verify(path)

    def test_solve_binds_exact_parent_receipt_and_requires_parent(self):
        first = self.receipt(name="first.json")
        second = self.receipt(name="second.json", decision_evidence="Another synthetic assumption decision")
        solve = self.receipt("solve", parent=first)
        with self.assertRaisesRegex(ValueError, "requires the signed assumptions"):
            self.verify(solve, "solve")
        with self.assertRaisesRegex(ValueError, "different assumptions"):
            self.verify(solve, "solve", second)

    def test_parent_reformatting_requires_a_new_linked_solve_receipt(self):
        parent = self.receipt()
        solve = self.receipt("solve", parent=parent)
        parent.write_text(json.dumps(json.loads(parent.read_text(encoding="utf-8")), indent=2), encoding="utf-8")
        self.verify(parent)
        with self.assertRaisesRegex(ValueError, "different assumptions"):
            self.verify(solve, "solve", parent)

    def test_future_old_or_naive_timestamp_is_rejected(self):
        values = [(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
                  (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), "2026-01-01T00:00:00"]
        for value in values:
            with self.subTest(value=value):
                path = self.receipt(approved_at=value)
                with self.assertRaisesRegex(ValueError, "timestamp"):
                    self.verify(path)

    def test_resume_requires_a_resume_plan_and_its_own_signed_action(self):
        assumptions = self.receipt()
        resume = self.receipt("resume", parent=assumptions)
        with self.assertRaisesRegex(ValueError, "plan operation"):
            self.verify(resume, "resume", assumptions)
        self.change_plan(operation="resume")
        assumptions = self.receipt()
        resume = self.receipt("resume", parent=assumptions)
        self.assertEqual(self.verify(resume, "resume", assumptions)["action_scope"], "resume")

    def test_changed_or_blocked_plan_cannot_be_approved(self):
        receipt = self.receipt()
        self.plan["operation"] = "resume"
        with self.assertRaisesRegex(ValueError, "Plan content changed"):
            self.verify(receipt)
        self.change_plan(checks={"valid": False})
        with self.assertRaisesRegex(ValueError, "blocking"):
            self.verify(receipt)

    def test_duplicate_json_fields_or_unsigned_additions_are_rejected(self):
        path = self.receipt()
        original = path.read_text(encoding="utf-8")
        path.write_text(original[:-1]+',"algorithm":"Ed25519"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.verify(path)
        envelope = json.loads(original)
        envelope["approved"] = True
        path.write_text(json.dumps(envelope), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "envelope"):
            self.verify(path)

    def test_keygen_emits_encrypted_key_and_never_overwrites(self):
        private_path, public_path = self.root / "generated-private.pem", self.root / "generated-public.pem"
        with patch.object(approvals, "_require_tty"), patch.object(approvals.getpass, "getpass", return_value=self.password.decode()):
            result = approvals.keygen_interactive(private_path, public_path)
            self.assertTrue(private_path.read_bytes().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"))
            self.assertEqual(result["public_key"], approvals.public_key_binding(public_path))
            with self.assertRaisesRegex(ValueError, "never overwritten"):
                approvals.keygen_interactive(private_path, public_path)

    def test_interactive_confirmation_produces_a_verifiable_receipt(self):
        path = self.root / "interactive-test.json"
        phrase = f"APPROVE assumptions {self.plan['content_digest'][:12]}"
        with patch.object(approvals, "_require_tty"), patch("builtins.input", side_effect=["TEST OPERATOR", "TEST ONLY", phrase]), \
             patch.object(approvals.getpass, "getpass", return_value=self.password.decode()), patch("builtins.print"):
            result = approvals.approve_interactive(self.plan, "assumptions", self.private_path, path, self.public_path)
        self.assertEqual(result["path"], str(path))
        self.assertEqual(self.verify(path)["approved_by"], "TEST OPERATOR")

    def test_declining_confirmation_writes_nothing(self):
        output = self.root / "declined.json"
        with patch.object(approvals, "_require_tty"), patch("builtins.input", side_effect=["TEST", "TEST", "NO"]), \
             patch.object(approvals.getpass, "getpass") as secret, patch("builtins.print"):
            with self.assertRaisesRegex(ValueError, "declined"):
                approvals.approve_interactive(self.plan, "assumptions", self.private_path, output, self.public_path)
            secret.assert_not_called()
        self.assertFalse(output.exists())

    def test_wrong_passphrase_or_unencrypted_key_cannot_approve(self):
        output = self.root / "rejected.json"
        phrase = f"APPROVE assumptions {self.plan['content_digest'][:12]}"
        with patch.object(approvals, "_require_tty"), patch("builtins.input", side_effect=["TEST", "TEST", phrase]), \
             patch.object(approvals.getpass, "getpass", return_value="INCORRECT TEST PASSWORD"), patch("builtins.print"):
            with self.assertRaisesRegex(ValueError, "unlock"):
                approvals.approve_interactive(self.plan, "assumptions", self.private_path, output, self.public_path)
        self.assertFalse(output.exists())
        self.private_path.write_bytes(self.private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        with patch.object(approvals, "_require_tty"), patch("builtins.input", side_effect=["TEST", "TEST", phrase]), \
             patch.object(approvals.getpass, "getpass") as secret, patch("builtins.print"):
            with self.assertRaisesRegex(ValueError, "encrypted PKCS8"):
                approvals.approve_interactive(self.plan, "assumptions", self.private_path, output, self.public_path)
            secret.assert_not_called()
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
