"""OCR cột Hán và dóng theo chỉ số neo như các script gốc."""
import io
import json
import os
import re
import sys
import time

import httpx
from google import genai
from google.genai import errors, types

from phase4_align_and_export import ROOT, annotation, valid_alignment

sys.path.insert(0, str(ROOT / "scripts"))
from Q3.build_new_guideline_submission import detect_han_column_boxes, split_han_lines_to_columns
from Q3.phase3_ocr_han import CASCADE_MODELS, check_repetition, parse_output


HAN_PAGES_WITH_OPTIONAL_PUNCTUATION = {211, 212}


def load_api_keys():
    names = ("GEMINI_API_KEYS", "GEMINI_API_KEY")
    values = [os.environ.get(name, "") for name in names]
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() in names:
                values.append(value)
    keys = {}
    for value in values:
        for key in value.strip().strip("\"'").split(","):
            key = key.strip()
            if key:
                keys[key] = None
    if not keys:
        raise ValueError("Cần GEMINI_API_KEY hoặc GEMINI_API_KEYS trong môi trường hoặc .env.")
    return keys


class GeminiQ4:
    def __init__(self, model):
        self.model = model
        self.models = list(dict.fromkeys((model, *CASCADE_MODELS, "gemini-3.5-flash-lite")))
        self.active_model = model
        self.last_alignment_model = None
        self.clients = [
            genai.Client(api_key=key, http_options={"timeout": 240_000})
            for key in load_api_keys()
        ]
        self.key_index = 0

    def generate_content(self, contents, config=None):
        while self.key_index < len(self.clients):
            try:
                return self.request_with_retry(self.clients[self.key_index], contents, config)
            except errors.APIError as error:
                invalid_key = error.code == 400 and "API_KEY_INVALID" in str(error.details)
                if error.code not in {401, 403} and not invalid_key:
                    raise RuntimeError(f"Gemini trả lỗi HTTP {error.code} khi gửi yêu cầu.") from error
                print(f"  API key số {self.key_index + 1} bị từ chối (HTTP {error.code}).", flush=True)
                self.key_index += 1
        raise RuntimeError("Không còn API key được Gemini chấp nhận. Kiểm tra quyền truy cập trong AI Studio.")

    def request_with_retry(self, client, contents, config):
        models = [self.active_model, *(model for model in self.models if model != self.active_model)]
        failures = {}
        rate_limits = {}
        delay = 15
        for attempt in range(3):
            retry_models = []
            retry_delay = delay
            for model in models:
                try:
                    response = client.models.generate_content(
                        model=model, contents=contents, config=config,
                    )
                    self.active_model = model
                    return response, model
                except httpx.TransportError:
                    failures[model] = "mất kết nối hoặc hết thời gian chờ"
                except errors.APIError as error:
                    if error.code not in {404, 429, 500, 502, 503, 504}:
                        raise
                    failures[model] = f"HTTP {error.code}"
                    print(f"  {model}: {failures[model]}", flush=True)
                    if error.code == 404:
                        continue
                    if error.code == 429:
                        details = str(error.details)
                        if re.search(r"requests per day|per_?day|daily quota|quota exceeded.*limit:\s*0", details, re.I):
                            failures[model] += " (hạn mức đã hết hoặc không khả dụng)"
                            continue
                        rate_limits[model] = rate_limits.get(model, 0) + 1
                        if rate_limits[model] >= 3:
                            continue
                        wait = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", details, re.I)
                        retry_delay = max(retry_delay, 60, int(float(wait[1])) + 1 if wait else 0)
                    else:
                        rate_limits.pop(model, None)
                retry_models.append(model)
            if not retry_models or attempt == 2:
                break
            print(f"  Chờ {retry_delay}s rồi thử lại phần đang xử lý.", flush=True)
            time.sleep(retry_delay)
            delay = min(2 * delay, 300)
            models = retry_models
        details = ", ".join(f"{model}: {error}" for model, error in failures.items())
        raise RuntimeError(f"Gemini chưa xử lý được yêu cầu sau các lần thử ({details}).")

    def request_ocr(self, images, *, correction=""):
        pages = ", ".join(str(page) for page in images)
        headers = "\n".join(f"=== PAGE {page:04d} ===\n<các cột Hán>" for page in images)
        prompt = (
            f"Chép nguyên văn các trang {pages} của Ấn Quang Pháp Sư Văn Sao, quyển IV. "
            "Các ảnh được gửi đúng thứ tự số trang ghi trên. "
            "Đọc cột dọc từ phải sang trái, trong mỗi cột đọc từ trên xuống. "
            "Giữ nguyên chữ Hán phồn thể và dị thể. Chép cả dấu ngắt bên cạnh chân chữ. "
            "Ghi dấu chấm tròn rỗng hoặc chấm tròn đặc dùng để ngắt câu thành 。, "
            "và dấu phẩy ngắt mệnh đề thành 、 đúng vị trí trên ảnh. "
            "Đặt chữ chú nhỏ song hành trong ngoặc （ ）. Bỏ chữ bản tâm và chữ ngoài khung. "
            "Giữ tiêu đề bài in trong chính văn. Không tự thêm hoặc suy đoán chữ và dấu. "
            "Mỗi cột vật lý một dòng, không nối cột hay thêm lời giải thích. "
            f"Trả về văn bản thuần theo mẫu:\n{headers}\n{correction}"
        )
        contents = [prompt]
        for image in images.values():
            buf = io.BytesIO()
            image.save(buf, "PNG")
            contents.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"))
        answer, _ = self.generate_content(contents)
        return parse_output((answer.text or "").strip().removesuffix("```").strip())

    def ocr_pages(self, images, body_pages):
        transcripts = self.request_ocr(images)
        failed = {}
        for page, image in images.items():
            try:
                boxes = han_boxes(image, transcripts.get(page, ""), page in body_pages, page=page)
            except ValueError as error:
                failed[page] = str(error)
            else:
                yield page, boxes
        for page, reason in failed.items():
            image = images[page]
            print(f"  Trang Hán {page}: {reason} Thử OCR riêng trang này.", flush=True)
            transcript = self.request_ocr({page: image}, correction=reason)
            try:
                boxes = han_boxes(image, transcript.get(page, ""), page in body_pages, page=page)
            except ValueError as error:
                raise ValueError(f"OCR Gemini trang Hán {page}: {error}") from error
            yield page, boxes

    def align(self, article, han, viet):
        self.last_alignment_model = None
        nh, nv = len(han), len(viet)
        if min(nh, nv) == 1:
            return [(0, nh, 0, nv)]
        prompt = (
            f"Dóng từng cụm tương ứng về nghĩa của bài {article} Hán–Việt. "
            "Trả về mảng JSON các cặp [hết_đoạn_Hán, hết_câu_Việt], chỉ số từ 1. "
            "Hai chỉ số tăng nghiêm ngặt, phủ liên tiếp cả hai văn bản. "
            f"Cặp cuối phải là [{nh},{nv}]. Tách nhỏ theo nội dung, không gộp đuôi để đủ số.\n"
            + "\n".join(f"H{i} {s}" for i,s in enumerate(han, 1)) + "\n"
            + "\n".join(f"V{i} {s}" for i,s in enumerate(viet, 1))
        )
        for attempt in range(3):
            response, model = self.generate_content(
                prompt, types.GenerateContentConfig(response_mime_type="application/json"))
            try:
                ends = json.loads(response.text or "")
            except ValueError:
                ends = None
            if isinstance(ends, list):
                path = []
                h = v = 0
                for end in ends:
                    if not isinstance(end, list) or len(end) != 2:
                        break
                    hn, vn = end
                    if type(hn) is not int or type(vn) is not int:
                        break
                    path.append((h, hn, v, vn))
                    h, v = hn, vn
                else:
                    if valid_alignment(path, nh, nv):
                        self.last_alignment_model = model
                        return path
            if attempt == 0:
                prompt += "\nLần trước chỉ số bị thiếu, sai hoặc gộp quá nhiều. Dóng lại từ đầu."
        raise ValueError(f"Bài {article}: Gemini trả ba kết quả dóng không hợp lệ. "
                         "Các bài đã hoàn thành được giữ trong cache.")


def han_boxes(image, transcription, body, *, page):
    char_count = len(re.findall(r"[\u3400-\u9fff\U00020000-\U000323AF]", transcription))
    if not char_count or check_repetition("".join(transcription.split())):
        raise ValueError("Thiếu văn bản Hán hoặc có chuỗi lặp.")
    if body and not 50 <= char_count <= 650:
        raise ValueError(f"Số chữ Hán ngoài khoảng kiểm tra ({char_count}).")
    # Phụ lục ở trang 211–212 vẫn cần box theo cột dù bản in thiếu dấu câu.
    if body and page not in HAN_PAGES_WITH_OPTIONAL_PUNCTUATION:
        # Một số trang cuối bài ngắn hơn chính văn. Dùng ngưỡng theo lượng chữ của trang.
        stops = sum(transcription.count(mark) for mark in "。！？")
        marks = stops + sum(transcription.count(mark) for mark in "、，；")
        if stops < max(1, char_count // 60) or marks < max(2, char_count // 30):
            raise ValueError(f"Quá ít dấu câu ({stops} dấu ngắt câu, {marks} dấu tổng cộng).")
    columns = split_han_lines_to_columns(transcription.splitlines())
    if not body:
        return [annotation("".join(columns), (0, 0, image.width, image.height))]
    if len(columns) > 13:
        raise ValueError(f"Gemini trả {len(columns)} cột, vượt quá 13 cột của trang.")
    return detect_han_column_boxes(image, columns)
