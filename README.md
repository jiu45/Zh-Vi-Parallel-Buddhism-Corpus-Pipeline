# Zh-Vi Parallel Buddhism Corpus Pipeline (Quy trình Xây dựng Ngữ liệu Song ngữ Hán - Việt)

Pipeline tự động hóa hoàn chỉnh để xây dựng ngữ liệu song ngữ Hán - Việt từ các tài liệu kinh điển, cổ tịch Phật giáo (PDF scan Hán văn và PDF kỹ thuật số tiếng Việt), bao gồm tiền xử lý ảnh, OCR thông minh (Gemini Vision API), chuẩn hóa văn bản, phân đoạn bài viết và căn chỉnh song ngữ tầng câu (hierarchical alignment).

---

## 📂 Cấu Trúc Thư Mục (Repository Structure)

```text
Zh-Vi-Parallel-Buddhism-Corpus-Pipeline/
│
├── CV09_AQPSVS_Q3/                     # Thư mục dữ liệu mẫu (hoặc cuốn sách cần xử lý)
│   ├── 01_nguon/                       # Tài liệu gốc đầu vào
│   │   ├── han/                        # PDF scan Hán văn (cổ bản, mộc bản)
│   │   └── viet/                       # PDF tiếng Việt
│   ├── 02_ocr_tho/                     # Kết quả OCR thô và file bảng theo quy chuẩn
│   │   ├── han/                        # Từng trang Hán văn (page_0001.txt, ...)
│   │   ├── viet/                       # Từng trang tiếng Việt (page_0001.txt, ...)
│   │   └── ocr_ket_qua_toan_bo.*       # CSV, JSON, XLSX chứa thông tin bbox, trang, nội dung
│   ├── 03_text_sach/                   # Toàn văn sách đã làm sạch hoàn chỉnh
│   │   ├── han.txt                     # Text Hán văn chuẩn
│   │   └── viet.txt                    # Text tiếng Việt chuẩn
│   └── 04_dong_hang/                   # Ngữ liệu song ngữ song hành sau căn chỉnh
│       ├── AQPSVS_Q3_parallel.tsv      # File TSV song ngữ (han_sentence, vi_sentence)
│       └── AQPSVS_Q3_parallel.xlsx     # File Excel song ngữ
│
├── metadata/                           # Dữ liệu đối chiếu, kiểm kê & checkpoint
│   ├── anchor_map.json                 # Bản đồ mỏ neo 110 bài văn (Tựa & Bạt)
│   ├── kiem_ke_nguon.md                # Báo cáo kiểm kê nguồn tài liệu
│   ├── han_articles.json               # Dữ liệu phân đoạn bài Hán văn
│   ├── viet_articles.json              # Dữ liệu phân đoạn bài tiếng Việt
│   ├── aligned_articles_cache.json     # Cache căn chỉnh chống mất dữ liệu khi gián đoạn
│   └── ocr_han_log.json                # Log chi tiết các lượt OCR
│
├── scripts/                            # Toàn bộ mã nguồn thực thi pipeline
│   ├── phase1_inventory_and_anchors.py # Bước 1: Kiểm kê tài liệu & lập Anchor Map
│   ├── phase2_extract_and_clean_viet.py# Bước 2: Trích xuất & làm sạch tiếng Việt
│   ├── phase3_ocr_han.py               # Bước 3.1: OCR Hán văn với Gemini Vision
│   ├── phase3_clean_and_segment_han.py # Bước 3.2: Làm sạch & phân đoạn Hán văn
│   ├── phase4_align_and_export.py      # Bước 4: Căn chỉnh song ngữ phân tầng & xuất ngữ liệu
│   └── generate_ocr_structured_output.py # Tạo file OCR chuẩn (CSV, JSON, XLSX có bbox)
│
├── .env.example                        # Mẫu cấu hình API key
├── .gitignore                          # Cấu hình bỏ qua môi trường ảo, cache & secrets
└── requirements.txt                    # Danh sách thư viện Python cần thiết
```

---

## 🚀 Cài Đặt Môi Trường (Installation)

### 1. Khởi tạo môi trường ảo (Virtual Environment)
```bash
# Clone repository
git clone https://github.com/jiu45/Zh-Vi-Parallel-Buddhism-Corpus-Pipeline.git
cd Zh-Vi-Parallel-Buddhism-Corpus-Pipeline

# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo:
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate
```

### 2. Cài đặt các thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### 3. Cấu hình Gemini API Keys
Sao chép file cấu hình mẫu và điền API key của bạn:
```bash
cp .env.example .env
```
Mở `.env` và thiết lập khóa của bạn:
```env
# 1 API key duy nhất cho OCR:
GEMINI_API_KEY=AIzaSy...

# Hoặc nhiều API keys (cách nhau bởi dấu phẩy) để tự động xoay tua khi chạm Rate Limit (RPM/RPD) ở Phase 4:
GEMINI_API_KEYS=AIzaSyKey1...,AIzaSyKey2...,AIzaSyKey3...
```

---

## 📖 Hướng Dẫn Chạy Pipeline Từng Bước (Execution Guide)

### Bước 1: Kiểm kê & Xây dựng Anchor Map
Trích xuất mục lục sách tiếng Việt, xác định phạm vi số trang, lập danh sách tiêu đề bài viết:
```bash
python scripts/phase1_inventory_and_anchors.py
```
*Kết quả:* Tạo ra `metadata/anchor_map.json` và `metadata/kiem_ke_nguon.md`.

### Bước 2: Trích xuất & Làm sạch văn bản Tiếng Việt
Trích xuất trực tiếp qua PyMuPDF bằng bộ lọc kích thước font (`font_size >= 12.5`), loại bỏ header/footer, xử lý ghép từ nối dòng (`-`), và tách câu:
```bash
python scripts/phase2_extract_and_clean_viet.py
```
*Kết quả:* Tạo ra `metadata/viet_articles.json` và `CV09_AQPSVS_Q3/03_text_sach/viet.txt`.

### Bước 3: Tiền xử lý & OCR Hán văn (Gemini Vision)
Tiền xử lý ảnh (Intensity Clipping ở 200 DPI), batch 5 trang/lượt gửi đến Gemini API với cơ chế kiểm định chất lượng (Inline QA Gate) và tự động thử lại:
```bash
python scripts/phase3_ocr_han.py
```
*Kết quả:* Lưu các trang thô vào `CV09_AQPSVS_Q3/02_ocr_tho/han/page_XXXX.txt`.

Sau đó chạy bước chuẩn hóa & phân đoạn bài viết tiếng Hán:
```bash
python scripts/phase3_clean_and_segment_han.py
```
*Kết quả:* Tạo ra `metadata/han_articles.json` và `CV09_AQPSVS_Q3/03_text_sach/han.txt`.

### Bước 4: Căn chỉnh song ngữ phân tầng (Hierarchical Sentence Alignment)
Sử dụng Anchor Matching triệt tiêu lỗi Domino Shift, tự động xoay tua API keys (Multi-Key Rotator) qua Gemini Flash để đối chiếu phân đoạn Hán - Việt:
```bash
python scripts/phase4_align_and_export.py
```
*Kết quả:* Xuất ngữ liệu hoàn chỉnh ra:
- `CV09_AQPSVS_Q3/04_dong_hang/AQPSVS_Q3_parallel.tsv`
- `CV09_AQPSVS_Q3/04_dong_hang/AQPSVS_Q3_parallel.xlsx`

### Bước 5 (Tùy chọn): Xuất bảng tổng hợp OCR chuẩn (CSV, JSON, XLSX có Bounding Box)
```bash
python scripts/generate_ocr_structured_output.py
```

---

## 🔄 Hướng Dẫn Đồng Đội Thay Sách Mới (How to Swap in Your Book)

Nếu đồng đội của bạn được giao quyển khác (ví dụ: Quyển I, Quyển II, hoặc một bộ kinh khác), hãy thực hiện các bước sau:

1. **Chuẩn bị thư mục dữ liệu mới:**
   Tạo thư mục mới theo đúng quy cách, ví dụ `CV09_AQPSVS_Q1/`:
   ```text
   CV09_AQPSVS_Q1/
   ├── 01_nguon/
   │   ├── han/      <- Đặt file PDF Hán văn của bạn vào đây
   │   └── viet/     <- Đặt file PDF tiếng Việt của bạn vào đây
   ├── 02_ocr_tho/
   │   ├── han/
   │   └── viet/
   ├── 03_text_sach/
   └── 04_dong_hang/
   ```

2. **Chỉ định thư mục qua biến môi trường (hoặc tham số):**
   Bạn có thể đặt biến môi trường `BOOK_DIR_NAME` trước khi chạy:
   ```bash
   # Windows PowerShell:
   $env:BOOK_DIR_NAME="CV09_AQPSVS_Q1"

   # Linux / macOS:
   export BOOK_DIR_NAME="CV09_AQPSVS_Q1"
   ```

3. **Cập nhật phạm vi trang & tiêu đề sách của bạn:**
   - Trong `scripts/phase1_inventory_and_anchors.py`: Điều chỉnh số trang mục lục (`range(start_toc, end_toc)`) và số trang chính văn của quyển mới.
   - Trong `scripts/phase3_clean_and_segment_han.py`: Cập nhật danh sách tiêu đề bài (`ARTICLE_SPECS`) tương ứng với mục lục của quyển mới.
   - Trong `scripts/phase3_ocr_han.py`: Điều chỉnh số trang bắt đầu (`--start-page`) và kết thúc (`--end-page`) khi chạy OCR.

4. **Chạy lần lượt các bước từ 1 đến 4** như hướng dẫn ở trên!

---

## 🔒 Bảo Mật & Quy Định Commit (Security & Git Rules)

- **Tuyệt đối không push file `.env`**: File này chứa API key riêng tư. `.gitignore` đã được cấu hình chặn file `.env`.
- **Môi trường ảo `.venv`** và các file bytecode `__pycache__` đã được loại trừ hoàn toàn khỏi Git.
- Cung cấp `.env.example` làm mẫu để mọi thành viên thiết lập môi trường an toàn và thống nhất.
