import argparse
import copy
import json
import sys
from pathlib import Path

import c2pa
from c2pa import Builder, C2paSignerInfo, C2paSigningAlg, Context, Signer

from common import (
    CERT_PATH,
    DEFAULT_GENERATOR,
    DEFAULT_TIMESTAMP_URL,
    KEY_PATH,
    MANIFEST_TEMPLATE_PATH,
    TRAINING_ALGORITHMIC_MEDIA,
    dump_json,
    ensure_parent,
    guess_format,
    parse_generator,
)

try:
    from c2pa import C2paBuilderIntent, C2paDigitalSourceType

    HAVE_INTENTS = True
except ImportError:
    HAVE_INTENTS = False


def _signing_alg():
    try:
        return C2paSigningAlg.PS256
    except AttributeError:
        return b"ps256"


def build_manifest_definition(
    template: dict,
    generator: str,
    mime: str,
    title: str,
    digital_source_type: str = TRAINING_ALGORITHMIC_MEDIA,
    use_intent: bool = False,
) -> dict:
    name, version = parse_generator(generator)
    manifest = copy.deepcopy(template) if template else {}
    manifest["claim_generator_info"] = [{"name": name, "version": version}]
    manifest["format"] = mime
    manifest["title"] = title
    assertions = manifest.get("assertions") or []
    actions_assertion = None
    for assertion in assertions:
        if assertion.get("label") == "c2pa.actions":
            actions_assertion = assertion
            break
    if actions_assertion is None:
        actions_assertion = {"label": "c2pa.actions", "data": {"actions": []}}
        assertions.append(actions_assertion)
    actions = (actions_assertion.setdefault("data", {}).get("actions")) or []
    if not any(a.get("action") == "c2pa.created" for a in actions):
        actions.insert(
            0,
            {
                "action": "c2pa.created",
                "digitalSourceType": digital_source_type,
            },
        )
    for action in actions:
        if action.get("action") == "c2pa.created":
            action["digitalSourceType"] = digital_source_type
    actions_assertion["data"]["actions"] = actions
    manifest["assertions"] = assertions
    if use_intent:
        manifest["assertions"] = [
            a for a in assertions if a.get("label") != "c2pa.actions"
        ] or []
    return manifest


def _can_use_intent(digital_source_type: str) -> bool:
    return (
        HAVE_INTENTS
        and digital_source_type == TRAINING_ALGORITHMIC_MEDIA
    )


def _apply_intent(builder: Builder) -> bool:
    if not HAVE_INTENTS:
        return False
    try:
        builder.set_intent(
            C2paBuilderIntent.CREATE,
            C2paDigitalSourceType.TRAINED_ALGORITHMIC_MEDIA,
        )
        return True
    except Exception:
        return False


def stamp_file(
    input_path,
    output_path,
    generator: str = DEFAULT_GENERATOR,
    cert_path=CERT_PATH,
    key_path=KEY_PATH,
    manifest_template=MANIFEST_TEMPLATE_PATH,
    digital_source_type: str = TRAINING_ALGORITHMIC_MEDIA,
    timestamp_url: str | None = DEFAULT_TIMESTAMP_URL,
) -> dict:
    input_path = Path(input_path)
    output_path = ensure_parent(output_path)
    fmt = guess_format(input_path)
    if fmt is None:
        raise ValueError(
            f"Unsupported file extension for '{input_path}'. "
            "Supported: jpg/jpeg/png/webp, mp4/mov, mp3/wav"
        )
    cert_path = Path(cert_path)
    key_path = Path(key_path)
    if not cert_path.exists() or not key_path.exists():
        raise FileNotFoundError(
            f"Missing signing cert/key. Expected '{cert_path}' and '{key_path}'. "
            "Run scripts/setup_dev_certs.sh first."
        )
    template = {}
    manifest_template = Path(manifest_template)
    if manifest_template.exists():
        template = json.loads(manifest_template.read_text(encoding="utf-8"))
    use_intent = _can_use_intent(digital_source_type)
    manifest_def = build_manifest_definition(
        template=template,
        generator=generator,
        mime=fmt.mime,
        title=input_path.name,
        digital_source_type=digital_source_type,
        use_intent=use_intent,
    )
    cert_data = cert_path.read_bytes()
    key_data = key_path.read_bytes()
    signer_kwargs = {
        "alg": _signing_alg(),
        "sign_cert": cert_data,
        "private_key": key_data,
    }
    if timestamp_url:
        signer_kwargs["ta_url"] = timestamp_url.encode("ascii")
    signer_info = C2paSignerInfo(**signer_kwargs)
    intent_applied = False
    with Context() as ctx:
        with Signer.from_info(signer_info) as signer:
            with Builder(json.dumps(manifest_def), ctx) as builder:
                if use_intent:
                    intent_applied = _apply_intent(builder)
                if output_path.exists():
                    output_path.unlink()
                builder.sign_file(
                    str(input_path), str(output_path), signer
                )
    return {
        "input": str(input_path),
        "output": str(output_path),
        "format": fmt.mime,
        "kind": fmt.kind,
        "generator": generator,
        "digital_source_type": digital_source_type,
        "intent_used": intent_applied,
        "timestamp_url": timestamp_url,
        "c2pa_sdk_version": getattr(c2pa, "sdk_version", lambda: "unknown")(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Gắn manifest C2PA (AI provenance) và ký số vào file media."
    )
    parser.add_argument("input", help="File media nguồn (jpg/png/webp/mp4/mov/mp3/wav)")
    parser.add_argument("output", help="File output đã gắn nhãn C2PA")
    parser.add_argument(
        "--generator",
        default=DEFAULT_GENERATOR,
        help="claim generator dạng 'Name/Version' (mặc định: %(default)s)",
    )
    parser.add_argument("--cert", default=str(CERT_PATH), help="Chứng chỉ PEM để ký")
    parser.add_argument("--key", default=str(KEY_PATH), help="Private key PEM để ký")
    parser.add_argument(
        "--manifest",
        default=str(MANIFEST_TEMPLATE_PATH),
        help="Template manifest JSON",
    )
    parser.add_argument(
        "--digital-source-type",
        default=TRAINING_ALGORITHMIC_MEDIA,
        help="digitalSourceType cho action c2pa.created",
    )
    parser.add_argument(
        "--ta-url",
        default=DEFAULT_TIMESTAMP_URL,
        help="Timestamp authority URL (rỗng để bỏ timestamp)",
    )
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Ký không kèm timestamp",
    )
    parser.add_argument(
        "--save-json",
        default=None,
        help="Lưu metadata kết quả stamp vào file JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Không in kết quả ra stdout",
    )
    args = parser.parse_args(argv)
    try:
        result = stamp_file(
            input_path=args.input,
            output_path=args.output,
            generator=args.generator,
            cert_path=args.cert,
            key_path=args.key,
            manifest_template=args.manifest,
            digital_source_type=args.digital_source_type,
            timestamp_url=None if args.no_timestamp else (args.ta_url or None),
        )
    except Exception as exc:
        print(f"[stamp] ERROR: {exc}", file=sys.stderr)
        return 2
    if args.save_json:
        dump_json(result, args.save_json)
    if not args.quiet:
        print(f"[stamp] OK: {result['input']} -> {result['output']}")
        print(f"[stamp] format={result['format']} generator={result['generator']}")
        print(f"[stamp] intent_used={result['intent_used']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
