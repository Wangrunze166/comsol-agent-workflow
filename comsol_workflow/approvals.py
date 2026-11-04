"""User-side Ed25519 approvals; the executor only receives a pinned public key.

Interactive checks prevent accidental pipeline use, not hostile PTY automation.
The signing key, its passphrase and the trust anchor must remain outside the
agent's authority. See docs/approval-security.md for that deployment boundary.
"""
import base64
import binascii
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import warnings

from .case import digest

DOMAIN = b"comsol-agent-workflow/approval/v1\0"
SCOPES = {"assumptions": "confirm_assumptions", "solve": "solve", "resume": "resume"}
PAYLOAD_FIELDS = {"stage", "action_scope", "content_digest", "approved", "approved_by",
                  "approved_at", "decision_evidence", "public_key_id", "parent_receipt_sha256"}


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except ImportError as exc:
        raise ValueError("Signed approvals require the optional dependency: pip install '.[approval]'") from exc
    return serialization, Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature


def _canonical(payload):
    return DOMAIN + json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")


def _require_tty():
    if not all(getattr(stream, "isatty", lambda: False)() for stream in (sys.stdin, sys.stdout, sys.stderr)):
        raise ValueError("Approval signing requires an interactive TTY; pipes and redirected streams are refused")


def _secret(prompt):
    # Fail instead of allowing getpass's echoing fallback on an unsuitable console.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            result = getpass.getpass(prompt)
        except getpass.GetPassWarning as exc:
            raise ValueError("A terminal with hidden passphrase entry is required") from exc
    if not result:
        raise ValueError("An empty private-key passphrase is not allowed")
    return result.encode("utf-8")


def _exclusive_write(path, content, mode=0o600):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


def _public(path):
    serialization, _, public_type, _ = _crypto()
    path = Path(path).resolve()
    content = path.read_bytes()
    key = serialization.load_pem_public_key(content)
    if not isinstance(key, public_type):
        raise ValueError("Approval trust anchor must be an Ed25519 public key")
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    binding = {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
               "keyid": hashlib.sha256(raw).hexdigest()}
    return key, binding


def public_key_binding(path):
    """Fingerprint an operator-provisioned public key; this does not establish trust."""
    return _public(path)[1]


def _checked_key(plan, path):
    key, binding = _public(path)
    expected = plan.get("approval_public_key")
    # The user-side signer may hold the same public key at a different path or
    # on a different machine. Trust binds the key bytes/identity, not a pathname.
    if not isinstance(expected, dict) or any(expected.get(k) != binding[k] for k in ("sha256", "keyid")):
        raise ValueError("Public key does not match the plan's pinned approval trust anchor")
    return key, binding


def _checked_plan(plan):
    unsigned = dict(plan)
    signature = unsigned.pop("content_digest", None)
    if not isinstance(signature, str) or digest(unsigned) != signature:
        raise ValueError("Plan content changed; regenerate it before obtaining signed approvals")
    if plan.get("checks", {}).get("valid") is not True:
        raise ValueError("Cannot approve a plan with blocking checks")
    try:
        created = datetime.fromisoformat(plan["created_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Plan requires a valid creation timestamp") from exc
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError("Plan creation timestamp must be timezone-aware and not in the future")
    return created


def _read_receipt(path):
    content = Path(path).read_bytes()
    if len(content) > 65536:
        raise ValueError("Approval receipt exceeds the supported size")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate approval JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite approval JSON number")

    receipt = json.loads(content.decode("utf-8-sig"), object_pairs_hook=pairs,
                         parse_constant=reject_constant)
    return receipt, hashlib.sha256(content).hexdigest()


def _verify(path, stage, plan, public_key_path, parent_receipt=None):
    if stage not in SCOPES:
        raise ValueError("Unknown approval stage")
    created = _checked_plan(plan)
    key, binding = _checked_key(plan, public_key_path)
    envelope, receipt_hash = _read_receipt(path)
    if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "algorithm", "keyid", "payload", "signature"}:
        raise ValueError("A signed approval envelope is required; a hand-edited approved=true JSON is not accepted")
    if type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1 or envelope["algorithm"] != "Ed25519" or envelope["keyid"] != binding["keyid"]:
        raise ValueError("Unsupported or untrusted approval signature")
    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS:
        raise ValueError("Invalid signed approval payload")
    invalid_signature = _crypto()[3]
    try:
        signature = base64.b64decode(envelope["signature"], validate=True)
        if len(signature) != 64:
            raise ValueError("Invalid signature length")
        key.verify(signature, _canonical(payload))
    except (ValueError, TypeError, binascii.Error, invalid_signature) as exc:
        raise ValueError("Approval signature verification failed") from exc
    if payload["stage"] != stage or payload["action_scope"] != SCOPES[stage] or payload["content_digest"] != plan["content_digest"] or payload["approved"] is not True or payload["public_key_id"] != binding["keyid"]:
        raise ValueError("Signed approval does not authorize this plan, stage or action")
    if stage != "assumptions" and plan.get("operation", "solve") != stage:
        raise ValueError("Signed action is incompatible with the plan operation")
    if not all(isinstance(payload[k], str) and payload[k].strip() for k in ("approved_by", "approved_at", "decision_evidence")):
        raise ValueError("Signed approval requires identity, timestamp and decision evidence")
    try:
        approved_at = datetime.fromisoformat(payload["approved_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid signed approval timestamp") from exc
    if approved_at.tzinfo is None or not created <= approved_at <= datetime.now(timezone.utc):
        raise ValueError("Signed approval timestamp must fall between plan creation and now")
    if stage == "assumptions":
        if payload["parent_receipt_sha256"] is not None:
            raise ValueError("Assumption approval must not have a parent receipt")
    else:
        if parent_receipt is None:
            raise ValueError("Solve/resume approval requires the signed assumptions receipt")
        parent, parent_hash = _verify(parent_receipt, "assumptions", plan, public_key_path)
        if payload["parent_receipt_sha256"] != parent_hash:
            raise ValueError("Solve/resume signature is bound to a different assumptions receipt")
        if approved_at < datetime.fromisoformat(parent["approved_at"].replace("Z", "+00:00")):
            raise ValueError("Solve/resume approval must follow assumption confirmation")
    return payload, receipt_hash


def verify_signed_receipt(path, stage, plan, public_key_path, parent_receipt=None):
    """Return authenticated payload; retain the ORIGINAL signed file for auditing."""
    return _verify(path, stage, plan, public_key_path, parent_receipt)[0]


def keygen_interactive(private_key_path, public_key_path):
    """Run on the user's trusted terminal; no password arguments or environment hook."""
    _require_tty()
    serialization, private_type, _, _ = _crypto()
    private_path, public_path = Path(private_key_path).resolve(), Path(public_key_path).resolve()
    if private_path == public_path or private_path.exists() or public_path.exists():
        raise ValueError("Choose distinct, new private/public key paths; existing keys are never overwritten")
    password = _secret("New private-key passphrase (hidden, at least 12 characters): ")
    if len(password.decode("utf-8")) < 12:
        raise ValueError("Use a private-key passphrase of at least 12 characters")
    if password != _secret("Repeat private-key passphrase (hidden): "):
        raise ValueError("Private-key passphrases differ")
    private = private_type.generate()
    encrypted = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.BestAvailableEncryption(password))
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    _exclusive_write(private_path, encrypted)
    _exclusive_write(public_path, public, 0o644)
    return {"private_key_path": str(private_path), "public_key": public_key_binding(public_path),
            "note": "Protect the private key and passphrase outside agent access; provision the public trust anchor independently."}


def approve_interactive(plan, stage, private_key_path, output, public_key_path, parent_receipt=None):
    """Sign one human decision after explicit TTY review and hidden key unlock."""
    _require_tty()
    _checked_plan(plan)
    _, binding = _checked_key(plan, public_key_path)
    if stage not in SCOPES or (stage != "assumptions" and plan.get("operation", "solve") != stage):
        raise ValueError("Approval stage is incompatible with the plan operation")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Approval output already exists; preserve prior decisions")
    parent_hash = None
    if stage != "assumptions":
        if parent_receipt is None:
            raise ValueError("Confirm assumptions first and provide its signed receipt")
        _, parent_hash = _verify(parent_receipt, "assumptions", plan, public_key_path)
    print(f"Action: {SCOPES[stage]}\nPlan: {plan['content_digest']}\nPublic key: {binding['keyid']}")
    print(f"Review bundle: {plan.get('run_dir', '(not provided)')}")
    print("Review the complete plan and engineering assumptions before signing. This authorizes only the displayed action.")
    identity = input("Your name or operator ID: ").strip()
    evidence = input("Decision note / review reference: ").strip()
    if not identity or not evidence:
        raise ValueError("Identity and decision note are required")
    phrase = f"APPROVE {stage} {plan['content_digest'][:12]}"
    if input(f"Type exactly '{phrase}' to approve: ").strip() != phrase:
        raise ValueError("Approval declined; no receipt was written")
    serialization, private_type, _, _ = _crypto()
    content = Path(private_key_path).read_bytes()
    if not content.lstrip().startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----"):
        raise ValueError("Signing requires an encrypted PKCS8 private key")
    password = _secret("Private-key passphrase (hidden): ")
    try:
        private = serialization.load_pem_private_key(content, password=password)
    except (ValueError, TypeError) as exc:
        raise ValueError("Cannot unlock the encrypted signing key") from exc
    if not isinstance(private, private_type):
        raise ValueError("Signing key must be Ed25519")
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if hashlib.sha256(raw).hexdigest() != binding["keyid"]:
        raise ValueError("Signing key does not match the pinned approval public key")
    payload = {"stage": stage, "action_scope": SCOPES[stage], "content_digest": plan["content_digest"],
               "approved": True, "approved_by": identity, "approved_at": datetime.now(timezone.utc).isoformat(),
               "decision_evidence": evidence, "public_key_id": binding["keyid"], "parent_receipt_sha256": parent_hash}
    envelope = {"schema_version": 1, "algorithm": "Ed25519", "keyid": binding["keyid"],
                "payload": payload, "signature": base64.b64encode(private.sign(_canonical(payload))).decode("ascii")}
    _exclusive_write(output, (json.dumps(envelope, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"path": str(output), "stage": stage, "content_digest": plan["content_digest"], "keyid": binding["keyid"]}
