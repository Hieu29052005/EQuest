import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
CERTS_DIR = PROJECT_ROOT / "certs"
CERT_PATH = CERTS_DIR / "cert.pem"
KEY_PATH = CERTS_DIR / "key.pem"
MANIFEST_TEMPLATE_PATH = SRC_DIR / "manifest.json"
ASSETS_INPUT_DIR = PROJECT_ROOT / "assets" / "input"
ASSETS_STAMPED_DIR = PROJECT_ROOT / "assets" / "stamped"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DOWNLOADED_DIR = RESULTS_DIR / "downloaded"
RESULTS_RAW_DIR = RESULTS_DIR / "raw"
REPORT_CSV_PATH = RESULTS_DIR / "report.csv"
REPORT_MD_PATH = RESULTS_DIR / "report.md"
VISIBLE_LABELS_PATH = RESULTS_DIR / "visible_labels.csv"

TRAINING_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)
DIGITAL_CAPTURE = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture"
)
COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/"
    "compositeWithTrainedAlgorithmicMedia"
)

IMAGE_EXTS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
VIDEO_EXTS = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}
AUDIO_EXTS = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".wave": "audio/wav",
}
MEDIA_EXTS = {**IMAGE_EXTS, **VIDEO_EXTS, **AUDIO_EXTS}

METHOD_TAGS = ("c2pa", "iptc", "wm", "none")
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
DEFAULT_GENERATOR = "EQuest-Stamp/1.0"
DEFAULT_WATERMARK_PAYLOAD = "EQUEST-AI-WM-V1"


@dataclass(frozen=True)
class MediaFormat:
    ext: str
    mime: str
    kind: str


def guess_format(path) -> MediaFormat | None:
    ext = Path(path).suffix.lower()
    if ext not in MEDIA_EXTS:
        return None
    mime = MEDIA_EXTS[ext]
    if ext in IMAGE_EXTS:
        kind = "image"
    elif ext in VIDEO_EXTS:
        kind = "video"
    else:
        kind = "audio"
    return MediaFormat(ext=ext, mime=mime, kind=kind)


def ensure_parent(path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(data, path, indent=2) -> None:
    ensure_parent(path)
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )


def parse_generator(value: str) -> tuple[str, str]:
    if "/" in value:
        name, version = value.split("/", 1)
        return name.strip(), version.strip()
    return value.strip(), "1.0"
