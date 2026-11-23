# 05_json_tach_bai — Tách 112 bài từ OCR Hán

Sinh từ `02_ocr_tho/han/page_*.txt` (216 trang OCR mộc bản) + `metadata/anchor_map.json`
(112 bài: section, article_num, vi_title, trang bản Việt).

## Kết quả

| Chỉ số | Giá trị |
| :--- | ---: |
| Số bài | **112** (THƯ TỪ 83 · LUẬN 8 · SỚ 21) |
| Số clause Hán | **14.767** (14.764 clause kết thúc bằng `。` + 3 ghi chú cuối bài) |
| Ký tự Hán | 107.812 |
| Clause ngoài 112 bài | 120 (= 60 clause trang 0002 + 60 clause trang 0217, bài kệ đầu/cuối quyển) |
| Tổng `。` toàn bộ OCR | 14.884 = 14.764 + 120 ✔ |

## Tệp

- `articles.json` — mảng 112 object, đúng schema yêu cầu và đúng thứ tự khoá:
  `global_id, section, article_num, vi_title, zh_title, content, clauses`.
- `articles/article_XXX.json` — mỗi bài một tệp, cùng một object.
- `danh_sach_bai.csv` — bảng tra: bài, tiêu đề Hán/Việt, trang Hán, trang Việt, số clause.
- `thong_ke_tach_bai.json` — thống kê theo phần + theo bài + danh sách cảnh báo.
- `build_articles_json.py` — script sinh lại toàn bộ.

## Quy tắc tách bài

1. Tiêu đề bài = dòng OCR **không có `。`, không có `、`**, không bắt đầu bằng `（`,
   dài ≤ 40 ký tự, và kết thúc bằng `書` / `論` / `疏` (kèm số thứ tự và/hoặc chú thích
   trong ngoặc, ví dụ `與徐蔚如居士書十二（戒磕頭布上打印）`).
2. Dòng chạy đầu trang bị loại khỏi chính văn: `印光法師文鈔卷二`,
   `印光法師文鈔卷二 （書 復馬舜卿居士書）`, `書`, `書二`, `論`, `疏`.
3. Tiêu đề lặp liền nhau trong cùng một trang (page_0126) chỉ tính một lần.
4. Gặp dòng bài kệ `…百偈…` (trang 0002, 0217) thì đóng bài hiện tại — đây là nội dung
   ngoài phạm vi 112 bài.
5. `content` = nối các dòng chính văn, bỏ khoảng trắng/xuống dòng.
6. `clauses` = tách theo `。`, giữ nguyên dấu, gộp mảnh cuối chỉ gồm dấu đóng ngoặc
   vào clause trước. Kiểm tra `"".join(clauses) == content` cho cả 112 bài: đạt.

## Đã kiểm chứng

- 112 tiêu đề phát hiện đúng bằng 112 bài trong `anchor_map.json`, đúng thứ tự:
  bài 1 = `復包右武居士書一` ↔ “91. Thư trả lời cư sĩ Bao Hữu Vũ (thư thứ nhất)”;
  bài 84 = `淨土決疑論` ↔ “1. Luận Tịnh độ quyết nghi”;
  bài 112 = `法雨寺建如意寮募緣疏（代撰）` ↔ “21. Sớ quyên mộ xây dựng liêu Như Ý…”.
- Cân đối dấu câu khớp tuyệt đối (14.884 = 14.764 + 120).
- Không bài nào rỗng; không còn dòng header lọt vào chính văn; không clause rỗng.

## Lưu ý

- Ba bài có clause cuối không kết thúc bằng `。` vì nguyên bản là ghi chú trong ngoặc:
  bài 25 `（方附集末）`, bài 90 `（本擬廣錄…遂止、）`, bài 92 `（下略）`, bài 100
  `…菩提矣。）`.
- `zh_title` lấy nguyên văn từ OCR (có thể còn lỗi nhận dạng như `佛敎`, `淸源`), cần
  đối chiếu khi in ấn.
- Chưa có nội dung tiếng Việt trong JSON: schema yêu cầu chỉ có `vi_title`. Có thể bổ
  sung `vi_content`/`vi_sentences` từ `03_text_sach/viet.txt` hoặc từ
  `02_ocr_tho/viet/` (5.190 câu) nếu cần.
