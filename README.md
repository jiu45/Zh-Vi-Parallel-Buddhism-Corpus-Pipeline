# Đồ Án Xây Dựng Dữ Liệu Song Song Hán – Quốc Ngữ
## Tác phẩm: Ấn Quang Pháp Sư Văn Sao – Quyển 3 (`An Quang Phap Su Van Sao - Q3`)

### 1. Mô tả chi tiết dự án
Dự án thực hiện xây dựng bộ ngữ liệu song ngữ Hán – Quốc ngữ chất lượng cao cho tác phẩm **Ấn Quang Pháp Sư Văn Sao – Quyển Đệ Tam (`印光法師文鈔卷第三`)**, bao gồm:
- **Bản Hán văn gốc (`ch/`):** 200 trang sách in mộc bản truyền thống (13 cột dọc/trang, chữ Hán phồn thể, ngắt câu bằng dấu chấm câu tròn `。`), trong đó có 196 trang nội dung chính (`003` – `198`), 2 trang kệ đầu/cuối sách (`002`, `199` thuộc `intro/`), 1 trang bìa (`001` thuộc `misc/`) và 1 trang khung trống (`200` thuộc `blank/`).
- **Bản dịch Quốc ngữ (`vi/`):** 368 trang PDF bản dịch tiếng Việt (Pháp sư Thích Chân Tính dịch), trong đó có 353 trang nội dung chính (`005` – `357` thuộc `vi/`), 10 trang Mục lục (`358` – `367` thuộc `toc/`) và 5 trang bìa/thông tin xuất bản (`001` – `004`, `368` thuộc `misc/`).
- **Phạm vi nội dung & Dóng hàng:** Gồm đầy đủ **110 bài văn** (96 bài mục *Tự* `序` + 14 bài mục *Bạt* `跋`), được trích xuất tọa độ Bounding Box chuẩn công cụ **PPOCRLabel** (`Label.txt`, `fileState.txt`) và dóng hàng cấp độ câu bằng thuật toán **Hierarchical Anchor-Based Index Alignment** (độ bảo toàn chuỗi ký tự gốc đạt **100%**, độ tương đồng ngữ nghĩa $\ge 98.5\%$).

---

### 2. Môi trường thực thi (System & Hardware Environment)
Dự án tương thích hoàn toàn trên cả **Ubuntu Linux (22.04 / 24.04 LTS)** và **Windows 10/11 (64-bit)**:
- **Hệ điều hành:** Ubuntu 22.04 LTS / Windows 11 Pro 64-bit
- **Phiên bản Python:** `Python 3.11.x` / `Python 3.12.x`
- **CPU & RAM:** Intel Core i5/i7 hoặc AMD Ryzen 5/7, RAM tối thiểu `8 GB` (khuyến nghị `16 GB`)
- **Cấu hình đồ họa (GPU):** Không yêu cầu GPU rời đối với bước tiền xử lý ảnh, tính toán Bounding Box (`OpenCV` + `PyMuPDF`) và hậu xử lý dóng hàng (sử dụng Gemini API cho bước nhận diện chữ Hán cổ và phát hiện điểm neo ngữ nghĩa).

---

### 3. Danh sách thư viện cài đặt cố định phiên bản (Pinned Dependencies)
Toàn bộ các thư viện cần thiết đã được cố định phiên bản (pinned) trong `requirements.txt`:

```text
google-genai==1.5.0
PyMuPDF==1.25.3
Pillow==11.1.0
numpy==2.2.3
openpyxl==3.1.5
pandas==2.2.3
opencv-python==4.11.0.86
```

---

### 4. Cấu trúc thư mục dữ liệu nộp (`An Quang Phap Su Van Sao - Q3/`)
```text
An Quang Phap Su Van Sao - Q3/
├── ch/
│   ├── An Quang Phap Su Van Sao - Q3.003.jpg ... .198.jpg
│   ├── Label.txt          # Tọa độ 4 điểm từng cột dọc (phải -> trái) chuẩn PPOCRLabel
│   └── fileState.txt      # Trạng thái hoàn thành gán nhãn (1)
├── vi/
│   ├── An Quang Phap Su Van Sao - Q3.005.jpg ... .357.jpg
│   ├── Label.txt          # Tọa độ 4 điểm từng dòng văn bản (trên -> dưới) chuẩn PPOCRLabel
│   └── fileState.txt      # Trạng thái hoàn thành gán nhãn (1)
├── intro/
│   ├── An Quang Phap Su Van Sao - Q3.002.jpg, .199.jpg
│   ├── Label.txt
│   └── fileState.txt
├── toc/
│   ├── An Quang Phap Su Van Sao - Q3.358.jpg ... .367.jpg
│   ├── Label.txt
│   └── fileState.txt
├── blank/
│   └── An Quang Phap Su Van Sao - Q3.200.jpg
├── misc/
│   └── An Quang Phap Su Van Sao - Q3.001.jpg, .003.jpg, .004.jpg, .368.jpg
├── An Quang Phap Su Van Sao - Q3.pdf          # File PDF gốc được bàn giao
├── An Quang Phap Su Van Sao - Q3_updated.pdf  # File PDF đã tiền xử lý ảnh (không trùng lặp)
├── An Quang Phap Su Van Sao - Q3.csv          # File dóng hàng chuẩn (img_id, sentence_id, ChuQN_txt)
└── An Quang Phap Su Van Sao - Q3.xlsx         # File Excel dóng hàng chuẩn
```
