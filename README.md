# EQuest — Gắn & kiểm tra nhãn "nội dung do AI tạo"

Công cụ Python gắn và xác minh nhãn **C2PA** (Content Credentials), đối chiếu
với **thẻ IPTC "Digital Source Type"** và **watermark ẩn**, phục vụ thực nghiệm
tỷ lệ sống sót của nhãn khi đăng lên Facebook / Zalo / TikTok / YouTube.

Xem `PLAN.md` để biết bối cảnh, so sánh 3 cách đánh dấu và lộ trình.

## Cấu trúc

```
EQuest/
├── certs/                  # cert dev self-signed (key.pem không commit)
├── src/
│   ├── manifest.json       # template manifest C2PA
│   ├── common.py           # hằng số & helper dùng chung
│   ├── c2pa_stamp.py       # D1 — gắn manifest C2PA + ký
│   ├── c2pa_verify.py      # D2 — đọc/validate manifest, phát hiện AI
│   ├── c2pa_report.py      # D3 — so sánh before/after, xuất CSV/Markdown
│   ├── iptc_tag.py         # D7 — ghi/đọc IPTC DigitalSourceType
│   └── watermark.py        # D8 — nhúng/đọc watermark ẩn
├── scripts/
│   ├── setup_dev_certs.sh  # tạo cert dev self-signed
│   └── make_sample_assets.py
├── assets/input|stamped/
├── results/downloaded|raw/
└── docs/test-protocol.md   # D5 — quy trình upload/download thủ công
```

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# exiftool (cho IPTC):  apt install libimage-exiftool-perl
bash scripts/setup_dev_certs.sh
python scripts/make_sample_assets.py
```

> Chứng chỉ sinh ra là **dev self-signed**, KHÔNG nằm trong trust list của các
> nền tảng. File vẫn verify được ở mức file, nhưng có thể không trigger nhãn
> hiển thị.

## Sử dụng

### 1. Gắn nhãn C2PA (D1)

```bash
python src/c2pa_stamp.py assets/input/cat.png assets/stamped/cat__c2pa.png
python src/c2pa_stamp.py clip.mp4 outputs/clip__c2pa.mp4 --generator "MyTool/2.0"
```

### 2. Kiểm tra C2PA (D2)

```bash
python src/c2pa_verify.py assets/stamped/cat__c2pa.png
python src/c2pa_verify.py file.jpg --json --save-json results/raw/x.json
# exit code: 0 = có manifest, 1 = không có
```

### 3. Gắn/đọc IPTC (D7)

```bash
python src/iptc_tag.py write assets/input/cat.png assets/stamped/cat__iptc.jpg
python src/iptc_tag.py read  assets/stamped/cat__iptc.jpg --json
```

### 4. Watermark ẩn (D8)

```bash
python src/watermark.py embed  assets/input/cat.png assets/stamped/cat__wm.png
python src/watermark.py detect assets/stamped/cat__wm.png
```

### 5. Báo cáo so sánh (D3)

```bash
python src/c2pa_report.py
# -> results/report.csv, results/report.md
```

## Quy ước đặt tên file tải về

`<platform>__<asset>__<method>__<tag>.<ext>`

- `platform`: facebook | zalo | tiktok | youtube
- `asset`: tên asset (cat, clip, voice...)
- `method`: download | screenshot | thirdparty | photo | file
- `tag`: c2pa | iptc | wm | none

Ví dụ: `tiktok__cat__download__c2pa.jpg`, `zalo__cat__file__iptc.jpg`.

## Quy trình thực nghiệm

Xem chi tiết tại `docs/test-protocol.md`. Tóm tắt:

1. Gắn nhãn 3 bản mỗi asset (`__c2pa`, `__iptc`, `__wm`), verify baseline.
2. Upload bản gốc lên nền tảng, ghi nhãn hiển thị.
3. Tải về nhiều đường, lưu vào `results/downloaded/` đúng quy ước.
4. Chạy `c2pa_report.py` để tổng hợp.

## Giới hạn

- **Cert dev self-signed** → nền tảng có thể không nhận diện để gắn nhãn.
- `manifest_present` vs `valid_binding` được tách riêng: mất nhãn ≠ chữ ký gãy.
- **IPTC không xác thực** — ai cũng sửa/giả được.
- **Watermark detector phân mảnh** — "không phát hiện" ≠ "không phải AI";
  `invisible-watermark` chỉ hỗ trợ ảnh.
- Hành vi nền tảng thay đổi theo thời gian — ghi rõ mốc thời gian test.
