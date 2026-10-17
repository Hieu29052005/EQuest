import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ASSETS_STAMPED_DIR,
    DEFAULT_WATERMARK_PAYLOAD,
    METHOD_TAGS,
    MEDIA_EXTS,
    REPORT_CSV_PATH,
    REPORT_MD_PATH,
    RESULTS_DOWNLOADED_DIR,
    RESULTS_RAW_DIR,
    VISIBLE_LABELS_PATH,
    dump_json,
)
from c2pa_verify import verify_file

try:
    from iptc_tag import read_dst
except Exception:
    read_dst = None

try:
    from watermark import check_image, DEFAULT_METHOD as WM_METHOD
except Exception:
    check_image = None
    WM_METHOD = "dwt-dct-svd"

COLUMNS = [
    "platform",
    "asset",
    "method",
    "tag",
    "manifest_present",
    "valid_binding",
    "ai_assertion",
    "iptc_dst",
    "watermark_detected",
    "visible_label",
]


def iter_media(directory) -> list[Path]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    )


def split_tag(stem: str) -> tuple[str, str]:
    for tag in METHOD_TAGS:
        suffix = f"__{tag}"
        if stem.endswith(suffix):
            return stem[: -len(suffix)], tag
    return stem, "none"


def parse_download_name(stem: str) -> dict:
    parts = stem.split("__")
    if len(parts) >= 4:
        platform, asset, method, tag = parts[0], parts[1], parts[2], parts[3]
    elif len(parts) == 3:
        platform, asset, method = parts
        tag = "none"
    elif len(parts) == 2:
        platform, asset = parts
        method, tag = "download", "none"
    else:
        platform, asset, method, tag = "unknown", stem, "download", "none"
    return {
        "platform": platform,
        "asset": asset,
        "method": method,
        "tag": tag,
    }


def check_file(path, wm_length: int, wm_method: str, trust_mode: str) -> dict:
    verify = verify_file(path, trust_mode=trust_mode)
    iptc_value = None
    if read_dst is not None:
        try:
            iptc_value = read_dst(path)
        except Exception:
            iptc_value = None
    wm_value = None
    if check_image is not None:
        wm_result = check_image(path, wm_length, wm_method)
        if wm_result is not None:
            wm_value = wm_result.get("detected")
    return {
        "manifest_present": verify["manifest_present"],
        "valid_binding": verify["signature_valid"],
        "ai_assertion": verify["is_ai"],
        "digital_source_type": verify["digital_source_type"],
        "iptc_dst": iptc_value,
        "watermark_detected": wm_value,
        "verify": verify,
        "error": verify.get("error"),
    }


def load_visible_labels(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    labels = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (
                row.get("platform", ""),
                row.get("asset", ""),
                row.get("method", ""),
                row.get("tag", ""),
            )
            labels[key] = row.get("visible_label", "unknown") or "unknown"
    return labels


def build_rows(stamped_dir, downloaded_dir, wm_length, wm_method, trust_mode):
    raw_dir = Path(RESULTS_RAW_DIR)
    rows = []
    baseline_index = {}
    for path in iter_media(stamped_dir):
        asset, tag = split_tag(path.stem)
        checks = check_file(path, wm_length, wm_method, trust_mode)
        dump_json(checks["verify"], raw_dir / f"baseline__{path.stem}.json")
        row = {
            "platform": "baseline",
            "asset": asset,
            "method": "baseline",
            "tag": tag,
            "manifest_present": checks["manifest_present"],
            "valid_binding": checks["valid_binding"],
            "ai_assertion": checks["ai_assertion"],
            "iptc_dst": checks["iptc_dst"],
            "watermark_detected": checks["watermark_detected"],
            "visible_label": "unknown",
        }
        rows.append(row)
        baseline_index[(asset, tag)] = row
    for path in iter_media(downloaded_dir):
        meta = parse_download_name(path.stem)
        checks = check_file(path, wm_length, wm_method, trust_mode)
        dump_json(checks["verify"], raw_dir / f"downloaded__{path.stem}.json")
        row = {
            "platform": meta["platform"],
            "asset": meta["asset"],
            "method": meta["method"],
            "tag": meta["tag"],
            "manifest_present": checks["manifest_present"],
            "valid_binding": checks["valid_binding"],
            "ai_assertion": checks["ai_assertion"],
            "iptc_dst": checks["iptc_dst"],
            "watermark_detected": checks["watermark_detected"],
            "visible_label": "unknown",
        }
        rows.append(row)
    return rows, baseline_index


def apply_visible_labels(rows, labels) -> None:
    for row in rows:
        key = (
            row["platform"],
            row["asset"],
            row["method"],
            row["tag"],
        )
        if key in labels:
            row["visible_label"] = labels[key]


def write_csv(rows, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in COLUMNS})


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def survival_summary(rows) -> list[dict]:
    buckets = {}
    for row in rows:
        if row["platform"] == "baseline":
            continue
        key = (row["platform"], row["tag"])
        bucket = buckets.setdefault(
            key,
            {"total": 0, "manifest": 0, "binding": 0, "ai": 0, "iptc": 0, "wm": 0},
        )
        bucket["total"] += 1
        bucket["manifest"] += int(bool(row["manifest_present"]))
        bucket["binding"] += int(bool(row["valid_binding"]))
        bucket["ai"] += int(bool(row["ai_assertion"]))
        bucket["iptc"] += int(bool(row["iptc_dst"]))
        bucket["wm"] += int(bool(row["watermark_detected"]))
    summary = []
    for (platform, tag), b in sorted(buckets.items()):
        total = b["total"] or 1
        summary.append(
            {
                "platform": platform,
                "tag": tag,
                "samples": b["total"],
                "manifest_present": f"{b['manifest']}/{total}",
                "valid_binding": f"{b['binding']}/{total}",
                "ai_assertion": f"{b['ai']}/{total}",
                "iptc_dst": f"{b['iptc']}/{total}",
                "watermark": f"{b['wm']}/{total}",
            }
        )
    return summary


def write_markdown(rows, summary, path, meta) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Báo cáo thực nghiệm — Nhãn nội dung AI (C2PA / IPTC / Watermark)")
    lines.append("")
    lines.append(f"- Thời điểm sinh báo cáo: {meta['generated_at']}")
    lines.append(f"- Thư mục baseline: `{meta['stamped_dir']}`")
    lines.append(f"- Thư mục tải về: `{meta['downloaded_dir']}`")
    lines.append(f"- Watermark method: `{meta['wm_method']}`")
    lines.append("")
    lines.append("## 1. Bảng kết quả chi tiết")
    lines.append("")
    if rows:
        lines.append("| " + " | ".join(COLUMNS) + " |")
        lines.append("|" + "|".join(["---"] * len(COLUMNS)) + "|")
        for row in rows:
            lines.append(
                "| " + " | ".join(_fmt(row.get(c)) for c in COLUMNS) + " |"
            )
    else:
        lines.append("_Chưa có dữ liệu. Chạy `c2pa_stamp.py` và upload/tải file trước._")
    lines.append("")
    lines.append("## 2. Tỷ lệ sống sót theo nền tảng × cách đánh dấu")
    lines.append("")
    if summary:
        lines.append(
            "| platform | tag | samples | manifest_present | valid_binding | "
            "ai_assertion | iptc_dst | watermark |"
        )
        lines.append("|" + "|".join(["---"] * 8) + "|")
        for s in summary:
            lines.append(
                f"| {s['platform']} | {s['tag']} | {s['samples']} | "
                f"{s['manifest_present']} | {s['valid_binding']} | "
                f"{s['ai_assertion']} | {s['iptc_dst']} | {s['watermark']} |"
            )
    else:
        lines.append("_Chưa có dữ liệu tải về để tính tỷ lệ._")
    lines.append("")
    lines.append("## 3. Phân tích & khuyến nghị")
    lines.append("")
    lines.append(
        "- Phân biệt rõ **manifest_present** (nhãn còn hay bị xoá) và "
        "**valid_binding** (chữ ký còn khớp hay file bị re-encode)."
    )
    lines.append(
        "- Đối chiếu C2PA/IPTC (metadata, mất khi re-encode) với watermark "
        "(bám nội dung, bền hơn) — xem `PLAN.md` mục 3."
    )
    lines.append(
        "- Khuyến nghị phòng thủ nhiều lớp: C2PA cho xác thực + IPTC khai báo "
        "nhanh + watermark cho độ bền."
    )
    lines.append("")
    lines.append("## 4. Giới hạn")
    lines.append("")
    lines.append(
        "- Chứng chỉ ký là **dev self-signed**, không nằm trong trust list của "
        "nền tảng → có thể không trigger nhãn hiển thị."
    )
    lines.append(
        "- Watermark chỉ đọc được bằng đúng thuật toán/payload đã nhúng; "
        "\"không phát hiện\" không có nghĩa \"không phải AI\"."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Đo lường & so sánh nhãn C2PA/IPTC/watermark before/after upload."
    )
    parser.add_argument("--stamped", default=str(ASSETS_STAMPED_DIR))
    parser.add_argument("--downloaded", default=str(RESULTS_DOWNLOADED_DIR))
    parser.add_argument("--out-csv", default=str(REPORT_CSV_PATH))
    parser.add_argument("--out-md", default=str(REPORT_MD_PATH))
    parser.add_argument("--visible-labels", default=str(VISIBLE_LABELS_PATH))
    parser.add_argument("--wm-method", default=WM_METHOD)
    parser.add_argument(
        "--wm-length",
        type=int,
        default=len(DEFAULT_WATERMARK_PAYLOAD.encode("utf-8")),
    )
    parser.add_argument(
        "--trust", choices=("dev", "official", "none"), default="dev"
    )
    args = parser.parse_args(argv)

    rows, _ = build_rows(
        args.stamped, args.downloaded, args.wm_length, args.wm_method, args.trust
    )
    labels = load_visible_labels(args.visible_labels)
    apply_visible_labels(rows, labels)
    summary = survival_summary(rows)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stamped_dir": args.stamped,
        "downloaded_dir": args.downloaded,
        "wm_method": args.wm_method,
    }
    write_csv(rows, args.out_csv)
    write_markdown(rows, summary, args.out_md, meta)
    print(f"[report] {len(rows)} dòng -> {args.out_csv}")
    print(f"[report] bảng markdown -> {args.out_md}")
    baseline = sum(1 for r in rows if r["platform"] == "baseline")
    downloaded = len(rows) - baseline
    print(f"[report] baseline={baseline} downloaded={downloaded}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
