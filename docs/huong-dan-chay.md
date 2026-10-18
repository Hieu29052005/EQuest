# Hướng dẫn chạy toàn bộ project EQuest

Tài liệu này hướng dẫn **từ đầu đến cuối** cách cài đặt, gắn nhãn, kiểm tra và
sinh báo cáo cho project gắn nhãn "nội dung do AI tạo" (C2PA / IPTC / Watermark).

Tham chiếu thêm: `PLAN.md` (kế hoạch & bối cảnh),
`docs/test-protocol.md` (quy trình upload thủ công).

---

## 1. Yêu cầu hệ thống

| Thành phần | Ghi chú |
|---|---|
| Python | 3.10 trở lên (khuyến nghị 3.11+) |
| pip / venv | Cài kèm Python |
| OpenSSL | Để tạo chứng chỉ dev (`openssl version`) |
| exiftool | Tuỳ chọn, cần cho IPTC (`exiftool -ver`) |

Cài `exiftool` (không bắt buộc nếu bỏ qua IPTC):

```bash
# Debian/Ubuntu
sudo apt install libimage-exiftool-perl
# macOS
brew install exiftool
```

---

## 2. Cài đặt project

Chạy trong thư mục gốc project:

```bash
cd /home/hieu/Downloads/Code/EQuest

# 1. Tạo & kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Cài thư viện Python
pip install --upgrade pip
pip install -r requirements.txt

# 3. Kiểm tra c2pa đã cài được
python -c "import c2pa; print('c2pa OK', c2pa.sdk_version())"
```

**Bảng xử lý nhanh sự cố cài đặt:**

| Lỗi | Cách xử lý |
|---|---|
| `ModuleNotFoundError: c2pa` | `pip install c2pa-python` (cần wheel cho OS của bạn) |
| Lỗi build `opencv-python` | Dùng `opencv-python-headless` (đã có trong requirements) |
| `imwatermark` thiếu | `pip install invisible-watermark` |
| `c2patool` (tuỳ chọn) | Dùng để đối chiếu CLI, xem repo `contentauth/c2patool` |

---

## 3. Cấu trúc thư mục

```
EQuest/
├── PLAN.md
├── README.md
├── docs/
│   ├── test-protocol.md      # quy trình upload/download
│   └── huong-dan-chay.md     # file này
├── requirements.txt
├── certs/                    # cert.pem + key.pem (dev self-signed)
├── src/
│   ├── common.py
│   ├── manifest.json
│   ├── c2pa_stamp.py         # D1
│   ├── c2pa_verify.py        # D2
│   ├── c2pa_report.py        # D3
│   ├── iptc_tag.py           # D7
│   └── watermark.py          # D8
├── scripts/
│   ├── setup_dev_certs.sh
│   └── make_sample_assets.py
├── assets/
│   ├── input/                # file AI gốc
│   └── stamped/              # file đã gắn nhãn
└── results/
    ├── downloaded/           # file tải về từ nền tảng
    ├── raw/                  # JSON manifest trích xuất
    ├── visible_labels.csv    # nhãn hiển thị nhập tay
    ├── report.csv            # sinh tự động
    └── report.md             # sinh tự động
```

---

## 4. Bước 1 — Tạo chứng chỉ dev (Phase 0)

```bash
bash scripts/setup_dev_certs.sh
```

Sinh ra `certs/cert.pem` và `certs/key.pem` (self-signed, RSA-2048, PS256).
`key.pem` đã được `.gitignore`, **không commit**.

Nếu muốn tạo thủ công:

```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -subj "/CN=EQuest Dev Signer" \
  -addext "keyUsage=digitalSignature" \
  -addext "extendedKeyUsage=emailProtection"
```

> ⚠️ Cert này **không** nằm trong trust list của Facebook/Google/... File vẫn
> verify được ở mức file nhưng nền tảng có thể không gắn nhãn hiển thị.

---

## 5. Bước 2 — Chuẩn bị assets AI (Phase 0)

```bash
python scripts/make_sample_assets.py
```

Sinh `assets/input/sample_image.png` và `assets/input/sample_audio.wav` để test
pipeline. Script **không** tạo video — bạn tự thêm 1 file `mp4/mov` do AI tạo vào
`assets/input/`.

Khuyến nghị đặt tên asset ngắn gọn để dùng cho quy ước file tải về, ví dụ:
`cat.png`, `clip.mp4`, `voice.wav`.

---

## 6. Bước 3 — Gắn nhãn C2PA (Phase 1 / D1)

**Cú pháp:**

```bash
python src/c2pa_stamp.py <input> <output> [--generator "Name/Version"]
```

**Ví dụ cho cả 3 loại:**

```bash
# Ảnh
python src/c2pa_stamp.py assets/input/cat.png        assets/stamped/cat__c2pa.png
# Video
python src/c2pa_stamp.py assets/input/clip.mp4       assets/stamped/clip__c2pa.mp4
# Audio
python src/c2pa_stamp.py assets/input/voice.wav      assets/stamped/voice__c2pa.wav

# Tuỳ chọn: đổi claim generator, không kèm timestamp (offline)
python src/c2pa_stamp.py assets/input/cat.png assets/stamped/cat__c2pa.png \
  --generator "MyTool/2.0" --no-timestamp
```

**Tùy chọn hữu ích:**

| Cờ | Ý nghĩa |
|---|---|
| `--generator` | `claim_generator` dạng `Name/Version` |
| `--cert` / `--key` | Đổi cert/key khác |
| `--manifest` | Template manifest JSON khác (`src/manifest.json`) |
| `--digital-source-type` | Đổi `digitalSourceType` của action `c2pa.created` |
| `--ta-url` / `--no-timestamp` | Timestamp authority / bỏ timestamp |
| `--save-json` | Lưu metadata kết quả stamp |
| `--quiet` | Không in kết quả |

Kết quả in ra: `[stamp] OK: ... -> ...` cùng `format`, `generator`,
`intent_used`.

---

## 7. Bước 4 — Gắn nhãn IPTC (Phase 6 / D7, tuỳ chọn)

Cần `exiftool`.

```bash
# Ghi "Created using Generative AI"
python src/iptc_tag.py write assets/input/cat.png assets/stamped/cat__iptc.jpg
python src/iptc_tag.py write assets/input/cat.png assets/stamped/cat__iptc.jpg \
  --value trainedAlgorithmicMedia

# Đọc lại
python src/iptc_tag.py read assets/stamped/cat__iptc.jpg --json
python src/iptc_tag.py read assets/stamped/cat__iptc.jpg --all   # toàn bộ XMP

# Xoá
python src/iptc_tag.py remove assets/stamped/cat__iptc.jpg
```

Giá trị alias được chấp nhận: `trainedAlgorithmicMedia`,
`created-using-generative-ai`, `trained-algorithmic-media`,
`digitalCapture`, `digital-capture`.

---

## 8. Bước 5 — Watermark ẩn (Phase 6 / D8, tuỳ chọn)

`invisible-watermark` **chỉ hỗ trợ ảnh** (jpg/jpeg/png/webp).

```bash
# Nhúng (mặc định payload "EQUEST-AI-WM-V1", method dwt-dct-svd)
python src/watermark.py embed assets/input/cat.png assets/stamped/cat__wm.png

# Tuỳ chọn payload & method
python src/watermark.py embed assets/input/cat.png assets/stamped/cat__wm.png \
  --payload "My-AI-Marker" --method dwt-dct

# Phát hiện
python src/watermark.py detect assets/stamped/cat__wm.png
# cần đúng độ dài payload, ví dụ payload 13 byte:
python src/watermark.py detect assets/stamped/cat__wm.png --length 13
```

Methods hợp lệ: `dwt-dct`, `dwt-dct-svd` (mặc định, bền hơn), `riva-gan`.

> Giá trị `--length` khi detect **phải khớp** số byte payload đã nhúng. Payload
> mặc định `EQUEST-AI-WM-V1` dài 15 byte.

---

## 9. Bước 6 — Kiểm tra / xác minh (Phase 2 / D2)

```bash
python src/c2pa_verify.py <file> [--json] [--raw] [--trust dev|official|none]
```

**Ví dụ:**

```bash
# File vừa ký
python src/c2pa_verify.py assets/stamped/cat__c2pa.png
python src/c2pa_verify.py assets/stamped/cat__c2pa.png --json

# Lưu JSON để đối chiếu baseline
python src/c2pa_verify.py assets/stamped/cat__c2pa.png --json \
  --save-json results/raw/baseline__cat__c2pa.json

# File gốc chưa ký -> manifest_present=false, exit code 1
python src/c2pa_verify.py assets/input/cat.png
echo $?    # = 1
```

**Đọc các trường quan trọng:**

| Trường | Ý nghĩa |
|---|---|
| `manifest_present` | Có manifest C2PA hay không |
| `signature_valid` | Chữ ký còn khớp (chưa re-encode) |
| `signer_trusted` | Cert ký có trong trust list (dev cert → thường false) |
| `is_ai` | Có assertion AI (`c2pa.created` + `trainedAlgorithmicMedia`) |
| `digital_source_type` | Giá trị source type tìm được |
| `validation_status` | Trạng thái validate đầy đủ của SDK |

> Phân biệt `manifest_present=false` (nhãn bị xoá) và
> `manifest_present=true` + `signature_valid=false` (file bị re-encode làm gãy
> chữ ký).

---

## 10. Bước 7 — Thực nghiệm upload/download thủ công (Phase 4)

Đây là bước **con người thao tác**, không tự động. Xem đầy đủ tại
`docs/test-protocol.md`. Tóm tắt:

1. Upload bản gốc đã gắn nhãn lên Facebook / Zalo / TikTok / YouTube.
2. Ghi lại nhãn AI hiển thị (yes/no/unknown).
3. Tải về nhiều đường (download, screenshot, file, photo, third-party).
4. Lưu file tải về vào `results/downloaded/` đúng quy ước tên.

**Quy ước tên file tải về:**

```
<platform>__<asset>__<method>__<tag>.<ext>
```

- `platform`: `facebook` | `zalo` | `tiktok` | `youtube`
- `asset`: `cat` | `clip` | `voice` | ...
- `method`: `download` | `screenshot` | `thirdparty` | `photo` | `file`
- `tag`: `c2pa` | `iptc` | `wm` | `none`

Ví dụ: `tiktok__cat__download__c2pa.jpg`, `zalo__cat__file__iptc.jpg`.

Ghi nhãn hiển thị vào `results/visible_labels.csv`:

```csv
platform,asset,method,tag,visible_label
tiktok,cat,download,c2pa,yes
zalo,cat,file,iptc,no
```

---

## 11. Bước 8 — Sinh báo cáo (Phase 3 / D3)

```bash
python src/c2pa_report.py
```

**Cú pháp đầy đủ:**

```bash
python src/c2pa_report.py \
  --stamped assets/stamped \
  --downloaded results/downloaded \
  --out-csv results/report.csv \
  --out-md results/report.md \
  --visible-labels results/visible_labels.csv \
  --wm-method dwt-dct-svd \
  --wm-length 15 \
  --trust dev
```

Kết quả:

- `results/report.csv` — bảng kết quả chi tiết (mỗi file 1 dòng).
- `results/report.md` — bảng Markdown + tỷ lệ sống sót theo nền tảng × tag.
- `results/raw/*.json` — manifest C2PA thô của từng file.

Các cột CSV: `platform, asset, method, tag, manifest_present, valid_binding,
ai_assertion, iptc_dst, watermark_detected, visible_label`.

> Báo cáo **chạy được cả khi chưa có file tải về** (chỉ có baseline).

---

## 12. Chạy toàn bộ nhanh (copy-paste)

```bash
cd /home/hieu/Downloads/Code/EQuest
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

bash scripts/setup_dev_certs.sh
python scripts/make_sample_assets.py

# Gắn nhãn 3 cách cho ảnh mẫu
python src/c2pa_stamp.py assets/input/sample_image.png assets/stamped/cat__c2pa.png
python src/iptc_tag.py   write assets/input/sample_image.png assets/stamped/cat__iptc.jpg
python src/watermark.py  embed assets/input/sample_image.png assets/stamped/cat__wm.png

# Verify baseline
python src/c2pa_verify.py assets/stamped/cat__c2pa.png --json \
  --save-json results/raw/baseline__cat__c2pa.json

# (Upload/tải về thủ công theo docs/test-protocol.md, bỏ file vào results/downloaded/)

# Sinh báo cáo
python src/c2pa_report.py
```

---

## 13. Bảng tóm tắt lệnh

| Việc | Lệnh |
|---|---|
| Tạo cert dev | `bash scripts/setup_dev_certs.sh` |
| Tạo asset mẫu | `python scripts/make_sample_assets.py` |
| Gắn C2PA | `python src/c2pa_stamp.py <in> <out>` |
| Ghi IPTC | `python src/iptc_tag.py write <in> <out>` |
| Đọc IPTC | `python src/iptc_tag.py read <file> --json` |
| Nhúng watermark | `python src/watermark.py embed <in> <out>` |
| Đọc watermark | `python src/watermark.py detect <file>` |
| Verify C2PA | `python src/c2pa_verify.py <file> --json` |
| Sinh báo cáo | `python src/c2pa_report.py` |

---

## 14. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `Missing signing cert/key` | Chưa chạy `setup_dev_certs.sh` |
| `Unsupported file extension` | Chỉ hỗ trợ jpg/jpeg/png/webp, mp4/mov, mp3/wav |
| `exiftool not found` | Cài exiftool hoặc bỏ qua các bước IPTC |
| `signer_trusted=false` | Bình thường với cert self-signed; dùng `--trust dev` để coi cert dev là user anchor |
| Watermark verify `detect=false` | Sai `--length`, sai method, hoặc file đã bị re-encode/xử lý |
| `manifest_present=false` ở file tải về | Metadata bị nền tảng strip — đây chính là kết quả cần ghi nhận |
| `valid_binding=false` nhưng còn manifest | File bị re-encode làm gãy chữ ký (khác với bị xoá nhãn) |

---

## 15. Ghi chú quan trọng

- Chỉ test bằng tài khoản của chính bạn; không đăng nội dung gây hiểu nhầm.
- Ghi rõ **mốc thời gian test** — hành vi nền tảng thay đổi theo thời gian.
- Kết quả `results/report.md` sẽ bị ghi đè mỗi lần chạy `c2pa_report.py`; các mục
  phân tích thủ công (mục 3–6) nên sao lưu/viết lại sau khi sinh bảng.
- Không nên commit `certs/key.pem`, `assets/`, `results/downloaded/`,
  `results/raw/` (đã có trong `.gitignore`).
