# Hướng Dẫn Sử Dụng & Tái Lập Quy Trình (USER GUIDE)

Tài liệu này hướng dẫn chi tiết từng bước để cài đặt môi trường và chạy lại toàn bộ quy trình (pipeline) từ đầu đến cuối trên một máy tính mới.

---

## 1. Cài đặt môi trường & Thư viện

### Bước 1.1: Tạo môi trường ảo Python (`venv`)
Trên **Ubuntu / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Trên **Windows (PowerShell)**:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 1.2: Cấu hình API Key cho mô hình Gemini
Tạo file `.env` (hoặc truyền biến môi trường) chứa danh sách Gemini API Key:
```env
GEMINI_API_KEY=your_primary_api_key_here
GEMINI_API_KEYS=your_key_1,your_key_2,your_key_3,your_key_4
```

---

## 2. Thông tin chi tiết về Mô hình & Prompt đã sử dụng

### 2.1. Mô hình OCR Chữ Hán Cổ (`scripts/phase3_ocr_han.py`)
- **Mô hình sử dụng:** `gemini-3.8-flash` và `gemini-3.6-flash` (qua SDK chính thức `google-genai`, API `client.interactions.create`, cấu hình `thinking_level="minimal"`).
- **Prompt OCR đã sử dụng:**
  ```text
  Bạn là chuyên gia OCR cổ tịch Hán văn Phật giáo (Ấn Quang Pháp Sư Văn Sao).
  Hãy trích xuất CHÍNH XÁC toàn bộ chữ Hán của từng trang theo thứ tự cột dọc từ PHẢI sang TRÁI, từ TRÊN xuống DƯỚI.
  QUY TẮC SỐNG CÒN:
  1. Giữ nguyên chữ Hán phồn thể/dị thể trên bản in mộc bản.
  2. Trên trang sách cứ sau mỗi cụm 4-8 chữ Hán đều có dấu chấm tròn rỗng (。). BẮT BUỘC giữ nguyên 100% mọi dấu câu (。) đúng vị trí trên ảnh (khoảng 60-80 dấu 。 mỗi trang), tuyệt đối không được bỏ sót dấu 。 nào!
  3. Các chữ in nhỏ song hành 2 hàng trong 1 cột (tiểu tự) hãy đặt trong ngoặc đơn （...）.
  4. Không lấy dòng chữ Bản tâm (tên sách và số trang) nằm ngoài khung dọc.
  ```
- **Kiểm định chất lượng tự động (Inline QA Gate):** Kiểm tra số lượng chữ Hán/trang (`300 - 600` chữ), mật độ dấu ngắt câu `。` ($\ge 1$ dấu / 15 chữ), phát hiện lặp chuỗi (n-gram repetition check).

### 2.2. Mô hình Dóng hàng phân cấp dựa trên điểm neo (`scripts/phase4_align_and_export.py`)
- **Mô hình sử dụng:** `gemini-3.6-flash` / `gemini-3.8-flash` / `gemini-3.5-flash-lite` kết hợp thuật toán cắt lát tất định (Deterministic Python Substring Slicing).
- **Prompt Dóng hàng đã sử dụng:**
  ```text
  Bạn là chuyên gia NLP ngữ liệu song ngữ Hán - Việt cổ.
  Nhiệm vụ: Dóng hàng ngữ liệu song ngữ cho Bài {gid}.
  Với mỗi câu tiếng Việt [V_j], hãy xác định chỉ số mệnh đề Hán văn bắt đầu [H_k].
  QUY TẮC CẦN TUÂN THỦ TUYỆT ĐỐI:
  1. Mọi câu tiếng Việt từ [V1] đến [V_M] phải được phủ kín, tuần tự từ 1 đến M.
  2. Với mỗi khối câu tiếng Việt [v_start, v_end], hãy trả về:
     - "v": [v_start, v_end]
     - "h_start": chỉ số nguyên của mệnh đề Hán văn BẮT ĐẦU tương ứng với câu tiếng Việt này (1-indexed).
  3. Chuỗi "h_start" phải tăng dần liên tục: câu đầu tiên V1 luôn có "h_start": 1; câu V_i quản lý từ H[h_start_i] đến H[h_start_{i+1} - 1].
  Chỉ trả về DUY NHẤT một mảng JSON hợp lệ: [{"v": [1, 1], "h_start": 1}, ...]
  ```

---

## 3. Trình tự chạy các lệnh Pipeline từ đầu đến cuối

### Bước 1: Kiểm kê nguồn & Xây dựng bản đồ 110 điểm neo cấp độ bài (Anchor Map)
```bash
python scripts/phase1_inventory_and_anchors.py
```
- **Đầu ra:** `metadata/anchor_map.json` (110 bài: 96 bài mục *Tự* + 14 bài mục *Bạt*).

### Bước 2: Trích xuất & Làm sạch văn bản Quốc ngữ
```bash
python scripts/phase2_extract_and_clean_viet.py
```
- **Đầu ra:** `metadata/viet_articles.json` và văn bản sạch `03_text_sach/viet.txt`.

### Bước 3: Tiền xử lý ảnh, chạy OCR Hán văn & Phân đoạn mệnh đề
```bash
python scripts/phase3_ocr_han.py --start-page 3 --end-page 198 --batch-size 5
python scripts/phase3_clean_and_segment_han.py
```
- **Đầu ra:** Các file OCR từng trang `02_ocr_tho/han/page_0001.txt` .. `page_0200.txt`, `metadata/han_articles.json`, và `03_text_sach/han.txt`.

### Bước 4: Chạy Dóng hàng Hán – Quốc ngữ cho toàn bộ 110 bài
```bash
python scripts/phase4_align_and_export.py
```
- **Đầu ra:** `metadata/aligned_articles_cache.json` và bộ file dóng hàng song ngữ.

### Bước 5: (Tùy chọn) Xuất bảng OCR 5 cột kèm Bounding Box PDF (theo mẫu Trợ giảng)
```bash
python scripts/generate_ocr_structured_output.py
```
- **Đầu ra:** `02_ocr_tho/ocr_ket_qua_{han,viet,toan_bo}.{csv,json,xlsx}`.

### Bước 6: Đóng gói toàn bộ dữ liệu theo chuẩn Guideline nộp bài mới (PPOCRLabel + CSV/XLSX)
```bash
python scripts/build_new_guideline_submission.py
```
- **Đầu ra:** Thư mục hoàn chỉnh `An Quang Phap Su Van Sao - Q3/` chứa:
  - `ch/`, `vi/`, `intro/`, `toc/`, `blank/`, `misc/` kèm `Label.txt` và `fileState.txt` đúng chuẩn **PPOCRLabel**.
  - `An Quang Phap Su Van Sao - Q3.pdf` và `An Quang Phap Su Van Sao - Q3_updated.pdf`.
  - `An Quang Phap Su Van Sao - Q3.csv` và `An Quang Phap Su Van Sao - Q3.xlsx`.

#### Dành cho thành viên làm Quyển 1, Quyển 2, Quyển 4:
Sau khi đã chạy xong 4 giai đoạn lõi (`phase1` $\rightarrow$ `phase4`), chỉ cần truyền tên thư mục quyển của bạn vào `build_new_guideline_submission.py`:
```bash
python scripts/build_new_guideline_submission.py \
    --book-name "An Quang Phap Su Van Sao - Q1" \
    --src-book-dir "CV09_AQPSVS_Q1" \
    --zh-misc-pages "1" \
    --zh-intro-pages "2,199" \
    --zh-blank-pages "200" \
    --vi-content-start 5 --vi-content-end 350 \
    --vi-toc-start 351 --vi-toc-end 360
```

---

## 4. Cách mở kiểm tra Bounding Box trên công cụ PPOCRLabel
1. Cài đặt PPOCRLabel:
   ```bash
   pip install PPOCRLabel
   PPOCRLabel --lang ch
   ```
2. Bấm **File $\rightarrow$ Open Dir** và chọn thư mục `An Quang Phap Su Van Sao - Q3/ch` (hoặc `An Quang Phap Su Van Sao - Q3/vi`).
3. PPOCRLabel sẽ tự động đọc `Label.txt` và `fileState.txt` trong thư mục đó và hiển thị toàn bộ các khung chữ nhật 4 điểm ôm sát từng cột chữ Hán / từng dòng chữ Quốc ngữ.
