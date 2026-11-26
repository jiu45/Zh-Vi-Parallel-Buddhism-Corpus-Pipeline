# Xử lý Ấn Quang Pháp Sư Văn Sao, Quyển IV

Pipeline cũng nhận `--quyen Q2`. Xem [cấu hình và cách chạy Q2](../Q2/README.md).

Chạy các lệnh từ thư mục gốc của repo trên macOS hoặc Linux. Đặt đúng một PDF Hán trong `CV09_AQPSVS_Q4/01_nguon/han/` và một PDF Việt trong `CV09_AQPSVS_Q4/01_nguon/viet/`. Bảng `page_layout.csv` áp dụng cho bản Hán 214 trang và bản Việt 400 trang. Số trang tính theo thứ tự trong PDF, bắt đầu từ 1.

## Cài đặt

```bash
python3.11 -m venv .venv-q4
.venv-q4/bin/python -m pip install -r scripts/Q4/requirements.txt
```

Lệnh Bash tự dùng `.venv-q4` nếu môi trường này có sẵn. OCR Hán và dóng hàng dùng Gemini. Đặt `GEMINI_API_KEY` hoặc `GEMINI_API_KEYS` trong môi trường hoặc trong `.env` ở gốc repo. Bản Việt lấy chữ sẵn có trong PDF. Script thử model dự phòng khi gặp lỗi dịch vụ và thử key cấu hình kế tiếp khi key hiện tại bị từ chối quyền truy cập.

## Chạy từng bước

| Việc cần làm | Lệnh |
|---|---|
| Kiểm tra hai PDF và phạm vi phân trang | `bash scripts/Q4/run_pipeline.sh kiem-tra` |
| Xuất JPG và bảng đối chiếu trang vào `anh_trang/` | `bash scripts/Q4/run_pipeline.sh anh` |
| OCR Hán bằng Gemini, xuất ảnh, nhãn PPOCRLabel và PDF Hán đã xử lý | `bash scripts/Q4/run_pipeline.sh ocr` |
| Tách và thống kê câu, mệnh đề từ nhãn hiện tại | `bash scripts/Q4/run_pipeline.sh tach-cau` |
| Dùng hai JSON metadata để dóng theo mốc bắt đầu Hán và tạo `sua.csv` | `bash scripts/Q4/run_pipeline.sh dong-hang` |
| Xem các cặp đã lưu trong một terminal khác | `bash scripts/Q4/run_pipeline.sh tien-do --theo-doi` |
| Tạo CSV/XLSX và ZIP từ bản `sua.csv` đã sửa | `bash scripts/Q4/run_pipeline.sh dong-goi` |
| Chạy từ OCR đến ZIP | `bash scripts/Q4/run_pipeline.sh all` |

Bước `anh` dùng riêng khi chỉ cần JPG. Bước `ocr` đã xuất ảnh cần cho nhãn. Các bước OCR, dóng hàng và đóng gói ghi vào `CV09_AQPSVS_Q4/ket_qua_moi/`. ZIP mặc định là `Q4.zip` trong thư mục này. Khi đóng gói để nộp, dùng `--nhom MSSV1_MSSV2 --bao-cao /duong/dan/bao-cao.pdf`. Có thể dùng thêm `--ten-sach` để đặt tên thư mục sách và hai bảng trong ZIP.

Khi thay bản OCR cũ bằng Gemini, script sao lưu `ket_qua_moi/` sau khi đã OCR thành công. Các lần chạy tiếp theo dùng lại bản Gemini đã tạo. Nếu thay PDF, bảng phân trang hoặc muốn nhận dạng lại bằng model khác, sao lưu `ket_qua_moi/` trước khi chạy OCR lại. Sau khi sửa nhãn hoặc mốc làm thay đổi văn bản, chạy `tach-cau` để tạo lại hai JSON trước khi chạy `dong-hang`. Khi tạo bảng dóng mới, script sao lưu `sua.csv` cũ nếu có.

Mỗi bài hoàn tất được lưu trong `.cache/dong_hang_q3_h_start_v1.json`. Chạy lại cùng lệnh để tiếp tục với những bài còn thiếu hoặc có đơn vị đầu vào thay đổi. Bảng dóng và cache theo cách trả chỉ số kết thúc trước đây được nhận diện là phương pháp khác.

Bước `tien-do` đọc các bài đã lưu và xuất `ket_qua_moi/sua_tam.csv` để xem cặp chính văn trước khi dóng xong. Có thể dùng `--theo-doi` để cập nhật bảng khi cache thay đổi trong lúc `dong-hang` đang chạy ở terminal khác. Dùng `Ctrl+C` trong terminal xem tiến độ để dừng theo dõi.

## Tách và thống kê trước khi dóng

Bước `tach-cau` đọc nhãn PPOCRLabel hiện tại và chia bài theo `anchor_map.csv`. Bản Việt lấy kiểu chữ và vị trí từ PDF để nhận diện tiêu đề, đoạn văn và dòng kệ. Hàm tách câu Q3 xử lý số có dấu chấm và chữ viết tắt. Bản Hán nối các cột theo thứ tự đọc, để riêng tiêu đề rồi tách mệnh đề theo `。`. Tiêu đề Tạp trước 35 được chép từ ảnh Hán trang 144 vì mốc OCR hiện tại bắt đầu ở cột chính văn.

Kết quả nằm trong `CV09_AQPSVS_Q4/metadata/`:

- `han_articles.json` lưu `zh_title`, `content` và `clauses` theo bài.
- `viet_articles.json` lưu `vi_title`, phạm vi trang, `paragraphs` và `sentences` theo bài.
- `thong_ke_tach_cau.json` đếm theo bài, theo phần và toàn quyển, liệt kê các bài thiếu vế Hán và đếm mệnh đề Hán dài hơn 120 ký tự để rà soát.

Hai JSON bài dùng chung `global_id`. Phụ lục 9–10 chỉ có bản ghi Việt và giữ mã bài. Thống kê tính chính văn của các bài có số thứ tự. Bước `tach-cau` chạy cục bộ và tạo hai JSON. Bước `dong-hang` lấy `clauses` và `sentences` trực tiếp từ hai file đã tạo, đối chiếu chúng với nhãn để gắn trang nguồn, rồi thêm tiêu đề thành một dòng riêng. Lệnh `all` tự tạo metadata khi chưa có file nào trong hai JSON này.

## Dùng kỹ thuật Gemini của script gốc

Có thể chọn model bằng `--model`.

- Gemini nhận dạng chữ Hán theo lô 3 trang và đọc cột dọc từ phải sang trái. Script dùng lại xử lý dấu câu, phát hiện văn bản lặp và dò khung cột của Q3. Trang chính văn có kiểm tra số chữ và dấu ngắt. Kết quả đạt kiểm tra được lưu theo từng trang, còn trang lỗi được thử lại riêng.
- Sau khi OCR, đối chiếu một số trang Hán với ảnh và kiểm tra các mốc trong `anchor_map.csv` trên nhãn mới. Script kiểm tra các mốc trước khi gửi bài đầu tiên để dóng.
- Q4 áp dụng cách dóng từng bài của Q3. `anchor_map.csv` liệt kê 38 bài Ký, 69 bài Tạp trước và 11 bài Phụ lục phía Việt. Mốc Việt là số bài ở đầu dòng trên trang đã ghi. Mốc Hán là một điểm trong box chữ của cột đầu bài trên ảnh 200 DPI. Bài Phụ lục 11 bắt đầu từ đầu trang Hán 211. Hai bài Phụ lục 9–10 chưa có mốc Hán được xác định nên được xuất một vế trong `sua.csv`. Phần danh sách ở cuối trang Hán 209 cũng được giữ riêng. Khi chỉnh nhãn làm mốc không còn khớp, đối chiếu điểm trong CSV với ảnh và box mới.
- Từng bài được gửi riêng qua `align_ranges()` của Q3. Gemini trả `v` và `h_start`. Hàm Q3 hiệu chỉnh các mốc và lấy mệnh đề Hán đến ngay trước mốc kế tiếp. Q4 kiểm tra thứ tự và độ phủ, rồi ghi mã bài, tên ảnh đầu và số trang cuối của từng vế vào `sua.csv`. Lớp gọi API Gemini vẫn sử dụng SDK và cơ chế thử lại đang được cấu hình cho Q4.

## Đối chiếu mã nguồn với Q3

`run_pipeline.sh` gọi `run_pipeline.py` để chọn công đoạn và kiểm tra PDF.

| Công đoạn Q3 | Vị trí tương ứng trong Q4 |
|---|---|
| Phase 1, kiểm kê và xác định mốc bài | `page_layout.csv` phân loại trang. `phase1_article_anchors.py` đọc `anchor_map.csv` để chia bài và giữ liên kết với trang nguồn. |
| Phase 2, trích và làm sạch tiếng Việt | Hàm `vietnamese()` tạo nhãn theo dòng từ PDF. `segment_articles.py` dựng đoạn và dùng lại hàm tách câu của Q3. |
| Phase 3, OCR và phân đoạn Hán | `phase3_render_page_images.py` xuất ảnh và chỉnh tương phản. `phase3_ocr_han.py` gọi Gemini cho OCR. `segment_articles.py` nối cột và tách mệnh đề Hán theo từng bài. |
| Phase 4, dóng hàng và xuất kết quả | `phase4_align_and_export.py` đọc hai JSON, dùng `align_ranges()` của Q3 qua lớp gọi Gemini trong `phase3_ocr_han.py`, xuất bảng và đóng gói. |

`phase4_align_e5.py` chứa phương pháp dóng E5 cũ để tham khảo.
