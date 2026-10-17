import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from imwatermark import WatermarkDecoder, WatermarkEncoder

from common import (
    DEFAULT_WATERMARK_PAYLOAD,
    IMAGE_EXTS,
    dump_json,
    ensure_parent,
    guess_format,
)

METHOD_MAP = {
    "dwt-dct": "dwtDct",
    "dwt-dct-svd": "dwtDctSvd",
    "riva-gan": "rivaGan",
}
DEFAULT_METHOD = "dwt-dct-svd"


def _method(value: str) -> str:
    if value in METHOD_MAP:
        return METHOD_MAP[value]
    if value in METHOD_MAP.values():
        return value
    raise ValueError(
        f"Unknown method '{value}'. Choose: {', '.join(METHOD_MAP)}"
    )


def _read_image(path) -> np.ndarray:
    fmt = guess_format(path)
    if fmt is None or fmt.ext not in IMAGE_EXTS:
        raise ValueError(
            "invisible-watermark chỉ hỗ trợ ảnh (jpg/jpeg/png/webp). "
            f"Không hỗ trợ: {Path(path).suffix or path}"
        )
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return image


def embed(
    input_path,
    output_path,
    payload: str = DEFAULT_WATERMARK_PAYLOAD,
    method: str = DEFAULT_METHOD,
) -> dict:
    image = _read_image(input_path)
    encoder = WatermarkEncoder()
    encoder.set_watermark("bytes", payload.encode("utf-8"))
    encoded = encoder.encode(image, _method(method))
    output_path = ensure_parent(output_path)
    if not cv2.imwrite(str(output_path), encoded):
        raise RuntimeError(f"Cannot write image: {output_path}")
    return {
        "input": str(input_path),
        "output": str(output_path),
        "payload": payload,
        "payload_bytes": len(payload.encode("utf-8")),
        "method": method,
    }


def detect(
    input_path,
    payload_length: int,
    method: str = DEFAULT_METHOD,
) -> dict:
    image = _read_image(input_path)
    decoder = WatermarkDecoder("bytes", payload_length)
    raw = decoder.decode(image, _method(method))
    raw_bytes = bytes(raw)
    try:
        payload = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        payload = None
    return {
        "file": str(input_path),
        "method": method,
        "payload_length": payload_length,
        "payload": payload,
        "raw_hex": raw_bytes.hex(),
        "detected": payload is not None,
    }


def check_image(path, payload_length: int, method: str = DEFAULT_METHOD):
    fmt = guess_format(path)
    if fmt is None or fmt.ext not in IMAGE_EXTS:
        return None
    try:
        result = detect(path, payload_length, method)
    except Exception:
        return None
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Nhúng & phát hiện watermark ẩn (invisible-watermark) để so sánh."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_embed = sub.add_parser("embed", help="Nhúng watermark ẩn vào ảnh")
    p_embed.add_argument("input")
    p_embed.add_argument("output")
    p_embed.add_argument(
        "--payload", default=DEFAULT_WATERMARK_PAYLOAD, help="Payload dạng text"
    )
    p_embed.add_argument(
        "--method", default=DEFAULT_METHOD, choices=tuple(METHOD_MAP)
    )
    p_embed.add_argument("--save-json", default=None)

    p_detect = sub.add_parser("detect", help="Phát hiện watermark ẩn trong ảnh")
    p_detect.add_argument("input")
    p_detect.add_argument(
        "--length",
        type=int,
        default=len(DEFAULT_WATERMARK_PAYLOAD.encode("utf-8")),
        help="Số byte payload đã nhúng",
    )
    p_detect.add_argument(
        "--method", default=DEFAULT_METHOD, choices=tuple(METHOD_MAP)
    )
    p_detect.add_argument("--save-json", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "embed":
            result = embed(args.input, args.output, args.payload, args.method)
            if args.save_json:
                dump_json(result, args.save_json)
            print(
                f"[wm] embedded {result['payload_bytes']} bytes "
                f"({args.method}) -> {result['output']}"
            )
            return 0
        result = detect(args.input, args.length, args.method)
        if args.save_json:
            dump_json(result, args.save_json)
        print(f"detected: {result['detected']}")
        print(f"payload: {result['payload']}")
        return 0 if result["detected"] else 1
    except Exception as exc:
        print(f"[wm] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
