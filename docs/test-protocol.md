# Test protocol — Upload/Download thủ công trên Facebook / Zalo / TikTok / YouTube

Mục tiêu: với mỗi **nền tảng × asset × cách đánh dấu**, xác định nhãn AI
(C2PA / IPTC / watermark) còn nguyên, bị suy biến hay bị xoá sau khi upload rồi
tải xuống.

> Chỉ test bằng **tài khoản của chính bạn**, không đăng nội dung gây hiểu nhầm.
> Ghi lại **ngày giờ test** vì hành vi nền tảng thay đổi theo thời gian.

---

## 0. Chuẩn bị một lần

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash scripts/setup_dev_certs.sh
python scripts/make_sample_assets.py     # tạo asset mẫu (ảnh + audio)
# thêm 1 video mp4/mov do AI tạo vào assets/input/
```

Ma trận test:

| Trục | Giá trị |
|---|---|
| Nền tảng | facebook, zalo, tiktok, youtube |
| Asset | `cat` (ảnh), `clip` (video), `voice` (audio) |
| Cách đánh dấu | `c2pa`, `iptc`, `wm` |
| Đường tải về | `download`, `screenshot`, `thirdparty`, `photo`, `file` |

---

## 1. Tạo bộ file đã gắn nhãn (baseline)

Với mỗi asset, tạo 3 bản:

```bash
# C2PA
python src/c2pa_stamp.py assets/input/cat.png assets/stamped/cat__c2pa.png

# IPTC
python src/iptc_tag.py write assets/input/cat.png assets/stamped/cat__iptc.jpg

# Watermark (chỉ ảnh)
python src/watermark.py embed assets/input/cat.png assets/stamped/cat__wm.png
```

Kiểm tra baseline (lưu JSON để đối chiếu):

```bash
python src/c2pa_verify.py assets/stamped/cat__c2pa.png --json \
  --save-json results/raw/baseline__cat__c2pa.json
python src/iptc_tag.py read assets/stamped/cat__iptc.jpg \
  --json --save-json results/raw/baseline__cat__iptc.json
python src/watermark.py detect assets/stamped/cat__wm.png \
  --save-json results/raw/baseline__cat__wm.json
```

**Điều kiện đạt baseline:** cả 3 phương pháp phát hiện được trên file gốc.

---

## 2. Quy trình cho mỗi tổ hợp

1. **Upload** file đã gắn nhãn **bản gốc**, KHÔNG qua editor/trình biên tập
   trung gian. Ghi lại: thời gian, dạng upload (post/story/chat/Shorts...).
2. **Quan sát nhãn hiển thị**: nền tảng có hiện nhãn "AI-generated / AI info"
   không? Ghi `yes / no / unknown`.
3. **Tải về nhiều đường** và lưu vào `results/downloaded/` theo quy ước:
   `<platform>__<asset>__<method>__<tag>.<ext>`
   - `download` — nút tải/save media gốc
   - `screenshot` — chụp màn hình
   - `file` — gửi nhận dạng file/tài liệu (Zalo)
   - `photo` — gửi dạng ảnh (bị nén, Zalo)
   - `thirdparty` — công cụ tải bên thứ 3
   - ví dụ: `tiktok__clip__download__c2pa.mp4`, `zalo__cat__file__iptc.jpg`
4. **Verify** file tải về (xem mục 3 bên dưới), lưu JSON vào `results/raw/`.
5. **(Phụ) Redistribution** — re-upload file đã bị strip lên nền tảng khác.

---

## 3. Lệnh verify file tải về

```bash
python src/c2pa_verify.py results/downloaded/tiktok__cat__download__c2pa.jpg --json
python src/iptc_tag.py read  results/downloaded/zalo__cat__file__iptc.jpg --json
python src/watermark.py detect results/downloaded/fb__cat__download__wm.jpg
```

Ghi nhận kết quả quan trọng:

| Trường | Ý nghĩa |
|---|---|
| `manifest_present` | Nhãn C2PA còn hay đã bị xoá |
| `valid_binding` | Chữ ký còn khớp (chưa re-encode) hay không |
| `ai_assertion` | Có assertion `trainedAlgorithmicMedia` |
| `iptc_dst` | Giá trị IPTC DigitalSourceType còn lại |
| `watermark_detected` | Watermark ẩn còn đọc được |
| `visible_label` | Nhãn hiển thị (nhập tay) |

> **Quan trọng:** phân biệt `manifest_present=false` (nhãn bị xoá) với
> `manifest_present=true, valid_binding=false` (file bị re-encode → chữ ký gãy).

---

## 4. Ghi chú riêng từng nền tảng

| Nền tảng | Điểm cần test |
|---|---|
| **Facebook** | Post cá nhân; so sánh file served vs file gốc; nhãn "AI info" lúc upload |
| **Zalo** | So sánh "Gửi ảnh" (bị nén) vs "Gửi file/tài liệu" (pass-through); chat 1-1 và nhóm |
| **TikTok** | Ảnh + video; ghi cả nhãn auto (từ C2PA) và nhãn self-disclosure |
| **YouTube** | Video/Shorts; nhãn auto, self-disclosure trong Studio, ghi chú mô tả |

---

## 5. Tổng hợp kết quả

Nhập `visible_label` (nhãn hiển thị quan sát được) vào `results/visible_labels.csv`:

```csv
platform,asset,method,tag,visible_label
tiktok,cat,download,c2pa,yes
zalo,cat,file,iptc,no
```

Sinh báo cáo:

```bash
python src/c2pa_report.py
# -> results/report.csv và results/report.md
```

---

## 6. Checklist mỗi tổ hợp

- [ ] Baseline đủ 3 phương pháp phát hiện
- [ ] Đã upload bản gốc, không qua editor
- [ ] Đã ghi nhãn hiển thị (yes/no/unknown)
- [ ] Đã lưu file tải về đúng quy ước tên
- [ ] Đã chạy verify + lưu JSON vào `results/raw/`
- [ ] Đã cập nhật `results/visible_labels.csv`
- [ ] Đã ghi ngày giờ test
