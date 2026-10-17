import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from common import (
    DIGITAL_CAPTURE,
    TRAINING_ALGORITHMIC_MEDIA,
    dump_json,
    ensure_parent,
)

EXIFTOOL = shutil.which("exiftool")
XMP_TAG = "XMP-iptcExt:DigitalSourceType"

VALUE_ALIASES = {
    "created-using-generative-ai": TRAINING_ALGORITHMIC_MEDIA,
    "trainedAlgorithmicMedia": TRAINING_ALGORITHMIC_MEDIA,
    "trained-algorithmic-media": TRAINING_ALGORITHMIC_MEDIA,
    "digitalCapture": DIGITAL_CAPTURE,
    "digital-capture": DIGITAL_CAPTURE,
}


def _require_exiftool() -> str:
    if not EXIFTOOL:
        raise RuntimeError(
            "exiftool not found. Install: apt install libimage-exiftool-perl "
            "(or brew install exiftool)"
        )
    return EXIFTOOL


def _resolve_value(value: str) -> str:
    return VALUE_ALIASES.get(value, value)


def read_all(path) -> dict:
    tool = _require_exiftool()
    proc = subprocess.run(
        [tool, "-j", "-G1", "-XMP-iptcExt:All", "-XMP:All", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"exiftool read failed: {proc.stderr.strip()}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Cannot parse exiftool output: {exc}") from exc
    return data[0] if data else {}


def read_dst(path) -> str | None:
    if not _require_exiftool():
        return None
    proc = subprocess.run(
        [EXIFTOOL, "-j", f"-{XMP_TAG}", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    record = data[0]
    return record.get("DigitalSourceType")


def write_dst(input_path, output_path, value=TRAINING_ALGORITHMIC_MEDIA) -> str:
    tool = _require_exiftool()
    input_path = Path(input_path)
    output_path = ensure_parent(output_path)
    resolved = _resolve_value(value)
    cmd = [
        tool,
        "-overwrite_original",
        f"-{XMP_TAG}={resolved}",
    ]
    if Path(output_path) != input_path:
        cmd += ["-o", str(output_path)]
    cmd.append(str(input_path))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"exiftool write failed: {proc.stderr.strip()}")
    return resolved


def remove_dst(path) -> None:
    tool = _require_exiftool()
    proc = subprocess.run(
        [tool, "-overwrite_original", f"-{XMP_TAG}=", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"exiftool remove failed: {proc.stderr.strip()}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ghi/đọc thẻ IPTC XMP DigitalSourceType bằng exiftool."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="Ghi DigitalSourceType")
    p_write.add_argument("input")
    p_write.add_argument("output")
    p_write.add_argument(
        "--value",
        default="trainedAlgorithmicMedia",
        help="Giá trị (mặc định: trainedAlgorithmicMedia / 'created using generative AI')",
    )

    p_read = sub.add_parser("read", help="Đọc DigitalSourceType")
    p_read.add_argument("input")
    p_read.add_argument("--all", action="store_true", help="In toàn bộ XMP")
    p_read.add_argument("--json", action="store_true", help="Xuất JSON")
    p_read.add_argument("--save-json", default=None)

    p_remove = sub.add_parser("remove", help="Xoá DigitalSourceType")
    p_remove.add_argument("input")

    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            resolved = write_dst(args.input, args.output, args.value)
            print(f"[iptc] wrote DigitalSourceType={resolved} -> {args.output}")
            return 0
        if args.command == "remove":
            remove_dst(args.input)
            print(f"[iptc] removed DigitalSourceType from {args.input}")
            return 0
        if args.all:
            data = read_all(args.input)
            result = {"file": str(args.input), "all": data}
        else:
            value = read_dst(args.input)
            result = {
                "file": str(args.input),
                "digital_source_type": value,
                "is_ai": value == TRAINING_ALGORITHMIC_MEDIA,
            }
        if args.save_json:
            dump_json(result, args.save_json)
        if args.json or args.all:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"digital_source_type: {result['digital_source_type']}")
            print(f"is_ai: {result['is_ai']}")
        return 0 if result.get("digital_source_type") else 1
    except Exception as exc:
        print(f"[iptc] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
