import argparse
import json
import sys
from pathlib import Path

from c2pa import Context, Reader, Settings

from common import (
    CERT_PATH,
    TRAINING_ALGORITHMIC_MEDIA,
    dump_json,
    guess_format,
)

OFFICIAL_ANCHORS_URL = "https://contentcredentials.org/trust/anchors.pem"

NEGATIVE_CODE_MARKERS = (
    "mismatch",
    "invalid",
    "failure",
    "failed",
    "malformed",
    "denied",
)
TRUST_FAILURE_MARKERS = ("untrusted", "certificate.chain", "cert.untrusted")


def _load_official_anchors() -> str:
    import urllib.request

    with urllib.request.urlopen(OFFICIAL_ANCHORS_URL, timeout=30) as response:
        return response.read().decode("utf-8")


def build_context(trust_mode: str = "dev") -> Context:
    settings_dict: dict = {"verify": {"verify_cert_anchors": True}}
    if trust_mode == "none":
        settings_dict["verify"] = {"verify_cert_anchors": False}
        return Context(Settings.from_dict(settings_dict))
    trust: dict = {}
    if Path(CERT_PATH).exists():
        trust["user_anchors"] = Path(CERT_PATH).read_text(encoding="utf-8")
    if trust_mode == "official":
        trust["trust_anchors"] = _load_official_anchors()
    if trust:
        settings_dict["trust"] = trust
    return Context(Settings.from_dict(settings_dict))


def _collect_validation(manifest: dict) -> list:
    entries = []
    validation_status = manifest.get("validation_status")
    if isinstance(validation_status, list):
        entries.extend(validation_status)
    signature_info = manifest.get("signature_info") or {}
    sig_status = signature_info.get("validation_status")
    if isinstance(sig_status, list):
        entries.extend(sig_status)
    return [e for e in entries if isinstance(e, dict)]


def _entry_code(entry: dict) -> str:
    return str(entry.get("code", "")).lower()


def _entry_failed(entry: dict) -> bool:
    if entry.get("success") is False:
        return True
    code = _entry_code(entry)
    return any(marker in code for marker in NEGATIVE_CODE_MARKERS)


def analyze_manifest_store(store: dict) -> dict:
    active_manifest = store.get("active_manifest")
    manifests = store.get("manifests") or {}
    result = {
        "manifest_present": bool(active_manifest and active_manifest in manifests),
        "signature_valid": False,
        "signer_trusted": False,
        "is_ai": False,
        "digital_source_type": None,
        "actions": [],
        "validation_status": [],
        "claim_generator": None,
        "active_manifest": active_manifest,
    }
    if not result["manifest_present"]:
        return result
    manifest = manifests[active_manifest]
    result["claim_generator"] = manifest.get("claim_generator")
    validation_entries = _collect_validation(manifest)
    result["validation_status"] = validation_entries
    failed = [e for e in validation_entries if _entry_failed(e)]
    result["signature_valid"] = not failed
    codes = [_entry_code(e) for e in validation_entries]
    trust_failed = any(
        any(marker in code for marker in TRUST_FAILURE_MARKERS) for code in codes
    )
    result["signer_trusted"] = result["signature_valid"] and not trust_failed
    actions = []
    source_types = []
    for assertion in manifest.get("assertions") or []:
        if not isinstance(assertion, dict):
            continue
        label = str(assertion.get("label", ""))
        if not label.startswith("c2pa.actions"):
            continue
        data = assertion.get("data") or {}
        for action in data.get("actions") or []:
            if not isinstance(action, dict):
                continue
            actions.append(action)
            dst = action.get("digitalSourceType")
            if dst:
                source_types.append(dst)
    result["actions"] = actions
    ai_source_types = [
        d for d in source_types if d == TRAINING_ALGORITHMIC_MEDIA
    ]
    result["is_ai"] = bool(ai_source_types)
    if ai_source_types:
        result["digital_source_type"] = ai_source_types[0]
    elif source_types:
        result["digital_source_type"] = source_types[0]
    return result


def empty_result(error: str | None = None) -> dict:
    result = {
        "manifest_present": False,
        "signature_valid": False,
        "signer_trusted": False,
        "is_ai": False,
        "digital_source_type": None,
        "actions": [],
        "validation_status": [],
        "claim_generator": None,
        "active_manifest": None,
    }
    if error:
        result["error"] = error
    return result


def verify_file(path, trust_mode: str = "dev", include_raw: bool = False) -> dict:
    path = Path(path)
    if not path.exists():
        return empty_result(error=f"File not found: {path}")
    try:
        with build_context(trust_mode) as ctx:
            with Reader(str(path), context=ctx) as reader:
                store = json.loads(reader.json())
    except Exception as exc:
        result = empty_result()
        result["error"] = str(exc)
        return result
    result = analyze_manifest_store(store)
    if include_raw:
        result["raw"] = store
    return result


def verify_stream(
    stream,
    mime: str,
    trust_mode: str = "dev",
    include_raw: bool = False,
) -> dict:
    try:
        with build_context(trust_mode) as ctx:
            with Reader(mime, stream, context=ctx) as reader:
                store = json.loads(reader.json())
    except Exception as exc:
        result = empty_result()
        result["error"] = str(exc)
        return result
    result = analyze_manifest_store(store)
    if include_raw:
        result["raw"] = store
    return result


def format_human(result: dict, path: str) -> str:
    lines = [
        f"file: {path}",
        f"manifest_present: {result['manifest_present']}",
        f"signature_valid: {result['signature_valid']}",
        f"signer_trusted: {result['signer_trusted']}",
        f"is_ai: {result['is_ai']}",
        f"digital_source_type: {result['digital_source_type']}",
        f"claim_generator: {result['claim_generator']}",
        f"active_manifest: {result['active_manifest']}",
        f"actions: {json.dumps(result['actions'], ensure_ascii=False)}",
        f"validation_status: {json.dumps(result['validation_status'], ensure_ascii=False)}",
    ]
    if result.get("error"):
        lines.append(f"error: {result['error']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Đọc & kiểm tra manifest C2PA, phát hiện assertion AI."
    )
    parser.add_argument("file", help="File media cần kiểm tra")
    parser.add_argument("--json", action="store_true", help="Xuất JSON ra stdout")
    parser.add_argument("--raw", action="store_true", help="Kèm manifest store thô")
    parser.add_argument(
        "--trust",
        choices=("dev", "official", "none"),
        default="dev",
        help=(
            "Cấu hình trust: dev = dùng cert dev local làm user anchor; "
            "official = trust anchors chính thức (cần mạng); none = bỏ verify trust"
        ),
    )
    parser.add_argument(
        "--save-json",
        default=None,
        help="Lưu kết quả verify vào file JSON",
    )
    args = parser.parse_args(argv)
    path = Path(args.file)
    fmt = guess_format(path)
    if fmt is None:
        print(
            f"[verify] WARNING: extension không hỗ trợ ({path.suffix}), "
            "vẫn thử đọc C2PA...",
            file=sys.stderr,
        )
    result = verify_file(path, trust_mode=args.trust, include_raw=args.raw)
    if args.save_json:
        dump_json(result, args.save_json)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_human(result, str(path)))
    return 0 if result["manifest_present"] else 1


if __name__ == "__main__":
    sys.exit(main())
