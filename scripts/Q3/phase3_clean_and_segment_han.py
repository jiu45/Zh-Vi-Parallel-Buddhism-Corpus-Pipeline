# -*- coding: utf-8 -*-
"""
Phase 3: Clean and Segment Han Articles (Complete 110 Articles of Volume 3)
- Reads all 196 OCR pages: page_0003.txt to page_0198.txt
- Cleans volume headers (印光法師文鈔卷第三), section headers (序, 跋), marginal headers
- Fixes cross-column inline parallel notes (e.g., Article 5)
- Accurately segments all 110 articles (96 TỰ + 14 BẠT) mapped to anchor_map.json
- Exports metadata/han_articles.json and 03_text_sach/han.txt
"""

import os
import sys
import re
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic project paths
BASE_DIR = Path(__file__).resolve().parent.parent
BOOK_DIR = BASE_DIR / os.environ.get("BOOK_DIR_NAME", "CV09_AQPSVS_Q3")
METADATA_DIR = BASE_DIR / "metadata"

ANCHOR_MAP_JSON = os.environ.get("ANCHOR_MAP_PATH", str(METADATA_DIR / "anchor_map.json"))
RAW_HAN_DIR = os.environ.get("RAW_HAN_DIR", str(BOOK_DIR / "02_ocr_tho" / "han"))
HAN_ARTICLES_JSON = os.environ.get("HAN_ARTICLES_JSON", str(METADATA_DIR / "han_articles.json"))
CLEAN_HAN_TXT = os.environ.get("CLEAN_HAN_TXT", str(BOOK_DIR / "03_text_sach" / "han.txt"))

# 110 Title Matchers: (global_id, section, article_num, zh_title, pattern_or_prefix)
ARTICLE_SPECS = [
    # --- 96 TỰ (Articles 1 to 96) ---
    (1, "TỰ", 1, "印施極樂圖序（代撰）", "印施極樂圖序"),
    (2, "TỰ", 2, "重刻佛說阿彌陀經序（代撰）", "重刻佛說阿彌陀經序"),
    (3, "TỰ", 3, "重刻彌陀略解圓中鈔勸持序", "重刻彌陀略解圓中鈔勸持序"),
    (4, "TỰ", 4, "隨自意三昧校正重刻序", "隨自意三昧校正重刻序"),
    (5, "TỰ", 5, "重刻石印普陀山志序", "重刻石印普陀山志序"),
    (6, "TỰ", 6, "紹興何閨仙家慶圖序", "紹興何閨仙家慶圖序"),
    (7, "TỰ", 7, "募設千僧齋序（代在家善人作）", "募設千僧齋序"),
    (8, "TỰ", 8, "重刻明宋文憲公護法錄序", "重刻明宋文憲公護法錄序"),
    (9, "TỰ", 9, "重刻龍舒淨土文題詞幷序（代王弘願作）", "重刻龍舒淨土文題詞幷序"),
    (10, "TỰ", 10, "佛學指南佛學起信編六道輪迴錄總序", "佛學指南佛學起信編六道輪迴錄總序"),
    (11, "TỰ", 11, "重刻安士全書序一", "重刻安士全書序一"),
    (12, "TỰ", 12, "重刻安士全書序二", "重刻安士全書序二"),
    (13, "TỰ", 13, "袁了凡四訓鑄板流通序", "袁了凡四訓鑄板流通序"),
    (14, "TỰ", 14, "四書蕅益解重刻序", "四書蕅益解重刻序"),
    (15, "TỰ", 15, "法華入疏序", "法華入疏序"),
    (16, "TỰ", 16, "普賢行願品疏鈔擷序", "普賢行願品疏鈔擷序"),
    (17, "TỰ", 17, "金剛經次詁序", "金剛經次詁序"),
    (18, "TỰ", 18, "金剛經綫說鑄板流通序", "金剛經綫說鑄板流通序"),
    (19, "TỰ", 19, "讚禮地藏菩薩懺願儀重刻序", "讚禮地藏菩薩懺願儀重刻序"),
    (20, "TỰ", 20, "揀魔辨異錄重刻序", "揀魔辨異錄重刻序"),
    (21, "TỰ", 21, "揀魔辨異錄石印序（代企覺居士趙希伊作）", "揀魔辨異錄石印序"),
    (22, "TỰ", 22, "三十二祖傳讚序", "三十二祖傳讚序"),
    (23, "TỰ", 23, "淨業良導序", "淨業良導序"),
    (24, "TỰ", 24, "佛學初階序", "佛學初階序"),
    (25, "TỰ", 25, "釋敎三字經序（代明天啓時。蜀東忠州。聚雲寺。吹萬老人釋廣眞作）", "釋敎三字經序"),
    (26, "TỰ", 26, "劉圓照居士摸象詩序", "劉圓照居士摸象詩序"),
    (27, "TỰ", 27, "佛學述要鑄板流通序", "佛學述要鑄板流通序"),
    (28, "TỰ", 28, "格言聯璧重刻序", "格言聯璧重刻序"),
    (29, "TỰ", 29, "不可錄重刻序", "不可錄重刻序"),
    (30, "TỰ", 30, "不可錄敦倫理序", "不可錄敦倫理序"),
    (31, "TỰ", 31, "普濟禪寺打交盤萬年簿序（代丁餘和尙作但打交盤未改十方）", "普濟禪寺打交盤萬年簿序"),
    (32, "TỰ", 32, "別庵統祖新公堂序（代茂量師作）", "別庵統祖新公堂序"),
    (33, "TỰ", 33, "眠雲公堂序（代法雨書記僧作）", "眠雲公堂序"),
    (34, "TỰ", 34, "通智法師公堂序（代悟開大師作）", "通智法師公堂序"),
    (35, "TỰ", 35, "立山老人派下子孫公堂序（代開如和尚作）", "立山老人派下子孫公堂序"),
    (36, "TỰ", 36, "募建藥王篷序（代撰）", "募建藥王篷序"),
    (37, "TỰ", 37, "法雨寺萬年簿序（代開和尚作）", "法雨寺萬年簿序"),
    (38, "TỰ", 38, "化聞老人公堂序（代開如和尚作）", "化聞老人公堂序"),
    (39, "TỰ", 39, "白華庵法譜序（此係懸敍。下敍事不錄）", "白華庵法譜序"),
    (40, "TỰ", 40, "香積會齋僧規約序", "香積會齋僧規約序"),
    (41, "TỰ", 41, "圓通庵萬年簿序（代永悟和尚作）", "圓通庵萬年簿序"),
    (42, "TỰ", 42, "永悟和尚公堂序（代本人作）", "永悟和尚公堂序"),
    (43, "TỰ", 43, "初機淨業指南序", "初機淨業指南序"),
    (44, "TỰ", 44, "藥師如來本願功德經重刻序", "藥師如來本願功德經重刻序"),
    (45, "TỰ", 45, "修正管理寺廟條例并護教文稿序", "修正管理寺廟條例并護教文稿序"),
    (46, "TỰ", 46, "江愼修先生放生殺生現報錄序", "江愼修先生放生殺生現報錄序"),
    (47, "TỰ", 47, "廈門流通佛經緣起序", "廈門流通佛經緣起序"),
    (48, "TỰ", 48, "法如庵萬年簿序（節錄懸敘）", "法如庵萬年簿序"),
    (49, "TỰ", 49, "傅大士傳錄序", "傅大士傳錄序"),
    (50, "TỰ", 50, "觀河集重刻序", "觀河集重刻序"),
    (51, "TỰ", 51, "觀無量壽佛經石印流通序", "觀無量壽佛經石印流通序"),
    (52, "TỰ", 52, "佛光月報序", "佛光者。十法界凡聖生佛即心本具之智體也"),
    (53, "TỰ", 53, "募修雲谷禪師塔院序", "募修雲谷禪師塔院序"),
    (54, "TỰ", 54, "西方公據重刻序", "西方公據重刻序"),
    (55, "TỰ", 55, "樂清虹橋淨土堂序", "樂清虹橋淨土堂序"),
    (56, "TỰ", 56, "阿彌陀經直解序", "阿彌陀經直解序"),
    (57, "TỰ", 57, "十三經讀本序", "十三經讀本序"),
    (58, "TỰ", 58, "以大乘入楞伽經斷食肉品誠神勿享肉食序（代安徽黔縣盧智睿居士作）", "以大乘入楞伽經斷食肉品誠神勿享肉食序"),
    (59, "TỰ", 59, "揚州普照寺同戒錄序", "揚州普照寺同戒錄序"),
    (60, "TỰ", 60, "重刻水陸儀軌序", "重刻水陸儀軌序"),
    (61, "TỰ", 61, "新昌大佛寺修樂放生池募緣序", "新昌大佛寺修樂放生池募緣序"),
    (62, "TỰ", 62, "金山江天禪寺傳戒序", "金山江天禪寺傳戒序"),
    (63, "TỰ", 63, "鄞縣至邱隘鎮修諸橋梁徵信錄序", "鄞縣至邱隘鎮修諸橋梁徵信錄序"),
    (64, "TỰ", 64, "淨土釋疑序", "淨土釋疑序"),
    (65, "TỰ", 65, "觀無量壽佛經善導疏重刻序", "觀無量壽佛經善導疏重刻序"),
    (66, "TỰ", 66, "京師第一監獄於甲子元旦普說三歸五戒序", "京師第一監獄於甲子元旦普說三歸五戒序"),
    (67, "TỰ", 67, "金剛經石刻序", "金剛經石刻序"),
    (68, "TỰ", 68, "佛遺教經解刊布流通序", "佛遺教經解刊布流通序"),
    (69, "TỰ", 69, "心經淺解序", "心經淺解序"),
    (70, "TỰ", 70, "觀世音菩薩本迹感應頌緣起序", "觀世音菩薩本迹感應頌緣起序"),
    (71, "TỰ", 71, "教觀綱宗釋義紀重刻序", "教觀綱宗釋義紀重刻序"),
    (72, "TỰ", 72, "上海世界居士林佛學研究叢書序", "上海世界居士林佛學研究叢書序"),
    (73, "TỰ", 73, "金剛經功德頌序", "金剛經功德頌序"),
    (74, "TỰ", 74, "儒釋一貫序", "儒釋一貫序"),
    (75, "TỰ", 75, "近代往生傳序", "近代往生傳序"),
    (76, "TỰ", 76, "慈悲道場懺法隨聞錄序（俗稱梁皇懺）", "慈悲道場懺法隨聞錄序"),
    (77, "TỰ", 77, "因果錄序", "因果錄序"),
    (78, "TỰ", 78, "生西金鑑序（後改作淨土淸鐘）", "生西金鑑序"),
    (79, "TỰ", 79, "棲真常住長年念佛序", "棲真常住長年念佛序"),
    (80, "TỰ", 80, "歸宗精舍同修淨業序", "歸宗精舍同修淨業序"),
    (81, "TỰ", 81, "臺灣佛教會緣起序", "臺灣佛教會緣起序"),
    (82, "TỰ", 82, "吳淞佛教居士林發隱序", "吳淞佛教居士林發隱序"),
    (83, "TỰ", 83, "秦川佛化隨刊序", "佛法者世出世間一切諸法之本源也"),
    (84, "TỰ", 84, "佛川敦本學校緣起序", "佛川敦本學校緣起序"),
    (85, "TỰ", 85, "千佛圖頌幷序", "千佛圖頌幷序"),
    (86, "TỰ", 86, "佛法要論序", "佛法要論序"),
    (87, "TỰ", 87, "普陀體仁施棺會緣起序", "普陀體仁施棺會緣起序"),
    (88, "TỰ", 88, "三聖堂萬年簿序", "三聖堂萬年簿序"),
    (89, "TỰ", 89, "蔡伯倫居士嚶鳴集序", "蔡伯倫居士嚶鳴集序"),
    (90, "TỰ", 90, "敎誨淺說序", "敎誨淺說序"),
    (91, "TỰ", 91, "橫超蓮社緣起序", "橫超蓮社緣起序"),
    (92, "TỰ", 92, "觀世音菩薩本迹感應頌重刻木板序", "觀世音菩薩本迹感應頌重刻木板序"),
    (93, "TỰ", 93, "阿彌陀經白話解釋序", "阿彌陀經白話解釋序"),
    (94, "TỰ", 94, "欲海回狂普勸受持流通序", "欲海回狂普勸受持流通序"),
    (95, "TỰ", 95, "壽康寶鑑序", "壽康寶鑑序"),
    (96, "TỰ", 96, "闢自由結婚邪說文序（代撰）", "闢自由結婚邪說文序"),

    # --- 14 BẠT (Articles 97 to 110) ---
    (97, "BẠT", 1, "歸心堂跋", "歸心堂跋"),
    (98, "BẠT", 2, "梵網經心地品菩薩戒疏注節要跋", "梵網經心地品菩薩戒疏注節要跋"),
    (99, "BẠT", 3, "石印異僧守松草書心經跋（以字迹相連、不能割裂、故未印）", "石印異僧守松草書心經跋"),
    (100, "BẠT", 4, "淸世宗御製普陀法雨寺碑文跋（乙卯年代趙希伊作）", "淸世宗御製普陀法雨寺碑文跋"),
    (101, "BẠT", 5, "六度室跋（代唐焦子作）", "六度室跋"),
    (102, "BẠT", 6, "心歸淨處跋（與劉智空居士作）", "心歸淨處跋"),
    (103, "BẠT", 7, "項伯吹先生定海縣監獄講經參觀記跋", "項伯吹先生定海縣監獄講經參觀記跋"),
    (104, "BẠT", 8, "往生論註跋", "往生論註跋"),
    (105, "BẠT", 9, "大總統敕令管理寺廟條例跋", "大總統敕令管理寺廟條例跋"),
    (106, "BẠT", 10, "藥師如來本願經重刻跋", "藥師如來本願經重刻跋"),
    (107, "BẠT", 11, "閱經室跋", "閱經室跋"),
    (108, "BẠT", 12, "信願念佛決定往生淺說跋", "信願念佛決定往生淺說跋"),
    (109, "BẠT", 13, "蓮榮堂跋", "蓮榮堂跋"),
    (110, "BẠT", 14, "鄧璞君義莊跋", "鄧璞君義莊跋"),
]

def load_all_pages():
    pages = {}
    for p in range(3, 199):
        fpath = os.path.join(RAW_HAN_DIR, f"page_{p:04d}.txt")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                pages[p] = f.read()
    return pages

def clean_and_segment_all():
    print(f"=== TIẾN HÀNH GHÉP NỐI VÀ LÀM SẠCH 110 BÀI VĂN HÁN (QUYỂN III) ===")
    
    with open(ANCHOR_MAP_JSON, "r", encoding="utf-8") as f:
        anchor_map = json.load(f)
    anchor_dict = {a['global_id']: a for a in anchor_map}
    
    pages = load_all_pages()
    print(f"Đã nạp {len(pages)} trang từ 3 đến 198.")
    
    # Build clean line stream
    stream_lines = []
    for p in range(3, 199):
        if p not in pages: continue
        raw = pages[p]
        for l in raw.splitlines():
            l_str = l.strip()
            if not l_str:
                continue
            # Remove volume header
            if p == 3 and l_str == "印光法師文鈔卷第三":
                continue
            # Remove section headers
            if p == 3 and l_str == "序":
                continue
            if p == 183 and l_str == "跋":
                continue
            # Remove duplicated running headers like '序 吳淞佛教居士林發隱序'
            if l_str.startswith("序 ") and len(l_str) <= 35:
                continue
            # Remove duplicated header of Article 81 on page 156
            if p == 156 and l_str == "臺灣佛教會緣起序":
                continue
            stream_lines.append(l_str)

    print(f"Tổng số dòng văn bản sau làm sạch sơ bộ: {len(stream_lines)}")

    # Locate each article in stream_lines
    article_locs = []
    curr_line_idx = 0
    
    for gid, section, anum, zh_title, pattern in ARTICLE_SPECS:
        found_idx = -1
        # Search from curr_line_idx forward
        for idx in range(curr_line_idx, len(stream_lines)):
            line = stream_lines[idx]
            # Match condition
            if pattern in line:
                # If title is in line and line is reasonably short (title line)
                if len(line) <= len(pattern) + 35 or pattern.startswith("佛光者") or pattern.startswith("佛法者世出世間"):
                    found_idx = idx
                    break
        if found_idx == -1:
            raise ValueError(f"Không tìm thấy vị trí bắt đầu cho Bài {gid} ({zh_title})!")
        article_locs.append((gid, section, anum, zh_title, found_idx))
        curr_line_idx = found_idx + 1

    print(f"-> Đã định vị thành công 110/110 bài văn trong luồng văn bản Hán.")

    # Slice content for each article
    articles = []
    for i in range(len(article_locs)):
        gid, section, anum, zh_title, start_line_idx = article_locs[i]
        if i < len(article_locs) - 1:
            end_line_idx = article_locs[i + 1][4]
        else:
            end_line_idx = len(stream_lines)

        # Get body lines
        # If the start line is a standalone title, content starts from start_line_idx + 1
        # If it's Article 52 or 83 (opening line is already content), include start line
        if ARTICLE_SPECS[i][4].startswith("佛光者") or ARTICLE_SPECS[i][4].startswith("佛法者世出世間"):
            body_lines = stream_lines[start_line_idx : end_line_idx]
        else:
            body_lines = stream_lines[start_line_idx + 1 : end_line_idx]

        raw_body = "".join(body_lines)
        raw_body = re.sub(r'\s+', '', raw_body)

        # Clean specific OCR artifacts
        if gid == 5:
            raw_body = re.sub(
                r'感應之[）\)](?:[（\(])?運、?微妙難思、?略書、?便?概、?以勖來哲、?[）\)]',
                '感應之道、微妙難思、略書梗概、以勖來哲。）',
                raw_body
            )

        # Split into clauses by '。'
        clauses = []
        raw_clauses = re.split(r'(。)', raw_body)
        c_i = 0
        while c_i < len(raw_clauses):
            c = raw_clauses[c_i].strip()
            if not c:
                c_i += 1
                continue
            punc = ""
            if c_i + 1 < len(raw_clauses) and raw_clauses[c_i + 1] == "。":
                punc = "。"
                c_i += 2
            else:
                c_i += 1
            clause_text = c + punc
            if clause_text:
                clauses.append(clause_text)

        vi_title = anchor_dict[gid]['vi_title']

        articles.append({
            'global_id': gid,
            'section': section,
            'article_num': anum,
            'vi_title': vi_title,
            'zh_title': zh_title,
            'content': raw_body,
            'clauses': clauses
        })

    # Save to han_articles.json
    os.makedirs(os.path.dirname(HAN_ARTICLES_JSON), exist_ok=True)
    with open(HAN_ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"-> Đã xuất thành công: {HAN_ARTICLES_JSON} ({len(articles)} bài)")

    # Save complete clean book text to han.txt (including Page 2 verse, volume title, 序, 跋, and Page 199 verse)
    os.makedirs(os.path.dirname(CLEAN_HAN_TXT), exist_ok=True)
    p2_lines = [l.strip() for l in open(os.path.join(RAW_HAN_DIR, "page_0002.txt"), encoding="utf-8").read().splitlines() if l.strip()]
    p199_lines = [l.strip() for l in open(os.path.join(RAW_HAN_DIR, "page_0199.txt"), encoding="utf-8").read().splitlines() if l.strip()]
    with open(CLEAN_HAN_TXT, "w", encoding="utf-8") as f:
        if p2_lines:
            f.write(f"{p2_lines[0]}\n\n{''.join(p2_lines[1:])}\n\n\n")
        f.write("印光法師文鈔卷第三\n\n")
        for a in articles:
            if a['global_id'] == 1:
                f.write("序\n\n")
            elif a['global_id'] == 97:
                f.write("跋\n\n")
            f.write(f"{a['zh_title']}\n\n")
            f.write(f"{a['content']}\n\n\n")
        if p199_lines:
            f.write(f"{p199_lines[0]}\n\n{''.join(p199_lines[1:])}\n")
    print(f"-> Đã xuất thành công: {CLEAN_HAN_TXT} ({os.path.getsize(CLEAN_HAN_TXT)} bytes)")

    return articles

def verify_results(articles):
    print("\n--- CHẠY KIỂM ĐỊNH TOÀN VẸN (VERIFICATION AUDIT) ---")
    assert len(articles) == 110, f"Lỗi: Số lượng bài ({len(articles)}) != 110!"
    
    empty_articles = [a['global_id'] for a in articles if len(a['content']) == 0]
    assert len(empty_articles) == 0, f"Lỗi: Các bài sau bị rỗng: {empty_articles}!"
    
    zero_clauses = [a['global_id'] for a in articles if len(a['clauses']) == 0]
    assert len(zero_clauses) == 0, f"Lỗi: Các bài sau không có clauses: {zero_clauses}!"

    tu_count = len([a for a in articles if a['section'] == 'TỰ'])
    bat_count = len([a for a in articles if a['section'] == 'BẠT'])
    assert tu_count == 96, f"Lỗi: Số bài TỰ ({tu_count}) != 96!"
    assert bat_count == 14, f"Lỗi: Số bài BẠT ({bat_count}) != 14!"

    total_chars = sum(len(a['content']) for a in articles)
    total_clauses = sum(len(a['clauses']) for a in articles)
    print(f"  [AUDIT PASS] 110 bài không rỗng (1..110): ĐẠT!")
    print(f"  [AUDIT PASS] Phân chia: 96 TỰ + 14 BẠT: ĐẠT!")
    print(f"  [AUDIT PASS] Tổng số chữ Hán toàn sách: {total_chars:,} ký tự.")
    print(f"  [AUDIT PASS] Tổng số mệnh đề (clauses): {total_clauses:,} mệnh đề.")
    print(f"  [AUDIT PASS] File han.txt tồn tại và kích thước: {os.path.getsize(CLEAN_HAN_TXT):,} bytes.")
    print("=== TOÀN BỘ GIAI ĐOẠN 3 ĐÃ HOÀN TẤT VÀ KIỂM CHỨNG THÀNH CÔNG RỰC RỠ! ===")

if __name__ == '__main__':
    articles = clean_and_segment_all()
    verify_results(articles)
