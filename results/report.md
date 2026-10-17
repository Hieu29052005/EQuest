# Báo cáo thực nghiệm — Nhãn nội dung AI (C2PA / IPTC / Watermark)

> Phần bảng ở mục 1–2 do `python src/c2pa_report.py` sinh tự động và ghi đè.
> Mục 3–6 điền thủ công sau khi có dữ liệu thực nghiệm.

## Phương pháp

- **Công cụ**: `src/c2pa_stamp.py` (gắn & ký C2PA), `src/iptc_tag.py`
  (IPTC XMP DigitalSourceType qua exiftool), `src/watermark.py`
  (invisible-watermark), `src/c2pa_verify.py` + `src/c2pa_report.py`.
- **Chứng chỉ ký**: dev self-signed (RSA-2048, PS256), KHÔNG trusted công khai.
- **Thời điểm test**: _<điền ngày giờ>_
- **Nền tảng**: Facebook, Zalo, TikTok, YouTube.
- **Quy trình upload/download**: xem `docs/test-protocol.md`.

## 1. Bảng kết quả chi tiết

_Chạy `python src/c2pa_report.py` để sinh bảng._

## 2. Tỷ lệ sống sót theo nền tảng × cách đánh dấu

_Chạy `python src/c2pa_report.py` để sinh bảng._

## 3. So sánh 3 cách đánh dấu

_<Điền nhận xét dựa trên tỷ lệ sống sót: C2PA/IPTC mất sớm ở mọi nền tảng;
watermark bền hơn nhưng phụ thuộc detector.>_

| Tiêu chí | C2PA | IPTC DST | Watermark ẩn |
|---|---|---|---|
| Sống sót qua upload/download | | | |
| Khả năng audit | | | |
| Chi phí triển khai | | | |

## 4. Quan sát nhãn hiển thị

_<Bảng nền tảng × asset × tag: có/không hiện nhãn AI; khác biệt giữa nền tảng.>_

## 5. Phân tích giới hạn

- Ảnh hưởng của dev self-signed cert (file verify được nhưng nền tảng có thể
  không gắn nhãn hiển thị).
- Giới hạn detector watermark (`invisible-watermark` chỉ hỗ trợ ảnh; "không
  phát hiện" ≠ "không phải AI").
- Hành vi nền tảng có thể thay đổi theo thời gian.

## 6. Khuyến nghị

- Ký bản master, upload bản gốc trực tiếp, không qua editor trung gian.
- Kết hợp nhiều lớp: C2PA (xác thực) + IPTC (khai báo nhanh) + watermark (bền).
- Không coi "không có nhãn" là bằng chứng "không phải AI".
