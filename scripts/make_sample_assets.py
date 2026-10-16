import math
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image, ImageDraw

from common import ASSETS_INPUT_DIR


def make_image(path: Path, size=(1024, 1024)) -> None:
    width, height = size
    image = Image.new("RGB", size, (24, 26, 42))
    draw = ImageDraw.Draw(image)
    for i in range(0, width, 64):
        color = (40 + i % 200, 60 + (i // 2) % 180, 120)
        draw.rectangle([i, 0, i + 32, height], fill=color)
    draw.ellipse(
        [width // 4, height // 4, width * 3 // 4, height * 3 // 4],
        outline=(240, 240, 250),
        width=12,
    )
    draw.text((40, 40), "AI SAMPLE (placeholder)", fill=(255, 255, 255))
    image.save(path)
    print(f"[assets] image -> {path}")


def make_audio(path: Path, seconds=3, rate=44100, freq=440.0) -> None:
    frames = bytearray()
    total = int(seconds * rate)
    for n in range(total):
        value = int(16000 * math.sin(2 * math.pi * freq * n / rate))
        frames += struct.pack("<h", value)
    with wave.open(str(path), "w") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(bytes(frames))
    print(f"[assets] audio -> {path}")


def main(argv=None) -> int:
    ASSETS_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    make_image(ASSETS_INPUT_DIR / "sample_image.png")
    make_audio(ASSETS_INPUT_DIR / "sample_audio.wav")
    print(
        "[assets] NOTE: cần tự thêm 1 file video (mp4/mov) do AI tạo "
        "vào assets/input/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
