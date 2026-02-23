"""카드뉴스 이미지 생성기 (Pillow 기반)."""
import io
import os

from PIL import Image, ImageDraw, ImageFont

# ── 템플릿 정의 ───────────────────────────────────────────

TEMPLATES = {
    "깔끔한 화이트": {
        "bg": "#FFFFFF",
        "title_color": "#1A1A1A",
        "body_color": "#333333",
        "accent": "#4A90D9",
        "muted": "#999999",
        "cover_bg": "#4A90D9",
        "cover_text": "#FFFFFF",
        "cover_sub": "#D0E4FF",
        "closing_bg": "#4A90D9",
        "closing_text": "#FFFFFF",
    },
    "다크 프리미엄": {
        "bg": "#1A1A2E",
        "title_color": "#FFFFFF",
        "body_color": "#E0E0E0",
        "accent": "#E94560",
        "muted": "#666680",
        "cover_bg": "#16213E",
        "cover_text": "#FFFFFF",
        "cover_sub": "#A0B4D0",
        "closing_bg": "#E94560",
        "closing_text": "#FFFFFF",
    },
    "수壽 브랜드": {
        "bg": "#FFF8F0",
        "title_color": "#2D1810",
        "body_color": "#4A3728",
        "accent": "#C4956A",
        "muted": "#B0A090",
        "cover_bg": "#2D1810",
        "cover_text": "#FFF8F0",
        "cover_sub": "#D4B896",
        "closing_bg": "#C4956A",
        "closing_text": "#FFFFFF",
    },
    "건강 그린": {
        "bg": "#F0F7F4",
        "title_color": "#1B4332",
        "body_color": "#2D6A4F",
        "accent": "#40916C",
        "muted": "#88B0A0",
        "cover_bg": "#1B4332",
        "cover_text": "#FFFFFF",
        "cover_sub": "#95D5B2",
        "closing_bg": "#40916C",
        "closing_text": "#FFFFFF",
    },
}

# ── 폰트 로딩 ─────────────────────────────────────────────

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

_FONT_PATHS = {
    "bold": [
        os.path.expanduser("~/Library/Fonts/Pretendard-Bold.otf"),
        os.path.join(_FONT_DIR, "Pretendard-Bold.otf"),
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
    "regular": [
        os.path.expanduser("~/Library/Fonts/Pretendard-Regular.otf"),
        os.path.join(_FONT_DIR, "Pretendard-Regular.otf"),
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
    "medium": [
        os.path.expanduser("~/Library/Fonts/Pretendard-Medium.otf"),
        os.path.join(_FONT_DIR, "Pretendard-Medium.otf"),
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
    "serif": [
        os.path.expanduser("~/Library/Fonts/MaruBuri-SemiBold.ttf"),
        os.path.join(_FONT_DIR, "MaruBuri-SemiBold.ttf"),
        os.path.expanduser("~/Library/Fonts/Pretendard-SemiBold.otf"),
    ],
}

_font_cache = {}


def _load_font(role, size):
    key = (role, size)
    if key in _font_cache:
        return _font_cache[key]
    for path in _FONT_PATHS.get(role, _FONT_PATHS["regular"]):
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# ── 렌더러 ────────────────────────────────────────────────


def _hex(color):
    """Hex 컬러를 RGB 튜플로 변환."""
    c = color.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


class CardNewsRenderer:
    """Pillow 기반 카드뉴스 이미지 생성기."""

    def __init__(self, template_name, size=(1080, 1080)):
        if template_name not in TEMPLATES:
            raise ValueError(f"알 수 없는 템플릿: {template_name}")
        self.t = TEMPLATES[template_name]
        self.w, self.h = size
        self.pad = 80

    def _new_image(self, bg_hex):
        return Image.new("RGB", (self.w, self.h), _hex(bg_hex))

    def _wrap_text(self, draw, text, font, max_width):
        """텍스트를 max_width에 맞게 줄바꿈."""
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                test = current + " " + word
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current = test
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _to_bytes(self, img):
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    # ── 표지 슬라이드 ──

    def render_cover(self, title, subtitle=""):
        img = self._new_image(self.t["cover_bg"])
        draw = ImageDraw.Draw(img)
        max_w = self.w - self.pad * 2

        # 제목
        font_title = _load_font("bold", 72)
        title_lines = self._wrap_text(draw, title, font_title, max_w)

        # 부제
        font_sub = _load_font("regular", 36)
        sub_lines = self._wrap_text(draw, subtitle, font_sub, max_w) if subtitle else []

        # 전체 높이 계산
        title_h = sum(
            draw.textbbox((0, 0), ln, font=font_title)[3]
            - draw.textbbox((0, 0), ln, font=font_title)[1]
            for ln in title_lines
        ) + max(0, len(title_lines) - 1) * 12

        gap = 40 if sub_lines else 0

        sub_h = 0
        if sub_lines:
            sub_h = sum(
                draw.textbbox((0, 0), ln, font=font_sub)[3]
                - draw.textbbox((0, 0), ln, font=font_sub)[1]
                for ln in sub_lines
            ) + max(0, len(sub_lines) - 1) * 8

        total_h = title_h + gap + sub_h
        y = (self.h - total_h) // 2

        # 제목 그리기
        for ln in title_lines:
            bbox = draw.textbbox((0, 0), ln, font=font_title)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            draw.text(
                ((self.w - lw) // 2, y),
                ln,
                font=font_title,
                fill=_hex(self.t["cover_text"]),
            )
            y += lh + 12

        if sub_lines:
            # 구분선
            y += 8
            line_w = min(200, max_w // 3)
            draw.line(
                [(self.w // 2 - line_w // 2, y), (self.w // 2 + line_w // 2, y)],
                fill=_hex(self.t["cover_sub"]),
                width=2,
            )
            y += 24

            # 부제 그리기
            for ln in sub_lines:
                bbox = draw.textbbox((0, 0), ln, font=font_sub)
                lw = bbox[2] - bbox[0]
                lh = bbox[3] - bbox[1]
                draw.text(
                    ((self.w - lw) // 2, y),
                    ln,
                    font=font_sub,
                    fill=_hex(self.t["cover_sub"]),
                )
                y += lh + 8

        return self._to_bytes(img)

    # ── 본문 슬라이드 ──

    def render_content(self, heading, body, slide_num=None, total_slides=None):
        img = self._new_image(self.t["bg"])
        draw = ImageDraw.Draw(img)
        max_w = self.w - self.pad * 2 - 20  # 왼쪽 accent bar 공간

        # 상단 포인트 바
        draw.rectangle(
            [(0, 0), (self.w, 6)], fill=_hex(self.t["accent"])
        )

        y = self.pad + 20

        # 소제목 (accent bar + heading)
        font_heading = _load_font("bold", 44)
        heading_lines = self._wrap_text(draw, heading, font_heading, max_w)

        # accent 세로 바
        heading_total_h = sum(
            draw.textbbox((0, 0), ln, font=font_heading)[3]
            - draw.textbbox((0, 0), ln, font=font_heading)[1]
            for ln in heading_lines
        ) + max(0, len(heading_lines) - 1) * 8

        bar_x = self.pad
        draw.rectangle(
            [(bar_x, y - 4), (bar_x + 4, y + heading_total_h + 4)],
            fill=_hex(self.t["accent"]),
        )

        # 소제목 텍스트
        text_x = self.pad + 20
        for ln in heading_lines:
            bbox = draw.textbbox((0, 0), ln, font=font_heading)
            lh = bbox[3] - bbox[1]
            draw.text(
                (text_x, y), ln, font=font_heading, fill=_hex(self.t["title_color"])
            )
            y += lh + 8

        y += 30

        # 본문
        font_body = _load_font("regular", 30)
        body_lines = self._wrap_text(draw, body, font_body, max_w)
        for ln in body_lines:
            bbox = draw.textbbox((0, 0), ln, font=font_body)
            lh = bbox[3] - bbox[1]
            if y + lh > self.h - self.pad - 40:
                draw.text(
                    (text_x, y), "...", font=font_body, fill=_hex(self.t["muted"])
                )
                break
            draw.text(
                (text_x, y), ln, font=font_body, fill=_hex(self.t["body_color"])
            )
            y += lh + 10

        # 페이지 번호
        if slide_num and total_slides:
            font_num = _load_font("medium", 26)
            num_text = f"{slide_num} / {total_slides}"
            bbox = draw.textbbox((0, 0), num_text, font=font_num)
            nw = bbox[2] - bbox[0]
            draw.text(
                (self.w - self.pad - nw, self.h - self.pad),
                num_text,
                font=font_num,
                fill=_hex(self.t["muted"]),
            )

        return self._to_bytes(img)

    # ── 마무리 슬라이드 ──

    def render_closing(self, cta_text, account_name=""):
        img = self._new_image(self.t["closing_bg"])
        draw = ImageDraw.Draw(img)
        max_w = self.w - self.pad * 2

        font_cta = _load_font("serif", 48)
        font_acc = _load_font("regular", 30)

        cta_lines = self._wrap_text(draw, cta_text, font_cta, max_w)

        cta_h = sum(
            draw.textbbox((0, 0), ln, font=font_cta)[3]
            - draw.textbbox((0, 0), ln, font=font_cta)[1]
            for ln in cta_lines
        ) + max(0, len(cta_lines) - 1) * 10

        acc_h = 0
        if account_name:
            bbox = draw.textbbox((0, 0), account_name, font=font_acc)
            acc_h = bbox[3] - bbox[1]

        gap = 50 if account_name else 0
        total_h = cta_h + gap + acc_h
        y = (self.h - total_h) // 2

        # CTA 텍스트
        for ln in cta_lines:
            bbox = draw.textbbox((0, 0), ln, font=font_cta)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            draw.text(
                ((self.w - lw) // 2, y),
                ln,
                font=font_cta,
                fill=_hex(self.t["closing_text"]),
            )
            y += lh + 10

        # 구분선 + 계정명
        if account_name:
            y += 10
            line_w = 120
            draw.line(
                [(self.w // 2 - line_w // 2, y), (self.w // 2 + line_w // 2, y)],
                fill=_hex(self.t["closing_text"]),
                width=1,
            )
            y += 20
            bbox = draw.textbbox((0, 0), account_name, font=font_acc)
            aw = bbox[2] - bbox[0]
            draw.text(
                ((self.w - aw) // 2, y),
                account_name,
                font=font_acc,
                fill=_hex(self.t["closing_text"]),
            )

        return self._to_bytes(img)

    # ── 전체 렌더 ──

    def render_all(self, slides_data):
        """모든 슬라이드를 렌더링하여 PNG bytes 리스트로 반환.

        slides_data 예시:
        [
            {"type": "cover", "title": "...", "subtitle": "..."},
            {"type": "content", "heading": "...", "body": "..."},
            {"type": "closing", "cta_text": "...", "account_name": "..."},
        ]
        """
        results = []
        total = len(slides_data)
        content_idx = 0
        content_total = sum(1 for s in slides_data if s["type"] == "content")

        for slide in slides_data:
            stype = slide["type"]
            if stype == "cover":
                results.append(
                    self.render_cover(slide.get("title", ""), slide.get("subtitle", ""))
                )
            elif stype == "content":
                content_idx += 1
                results.append(
                    self.render_content(
                        slide.get("heading", ""),
                        slide.get("body", ""),
                        slide_num=content_idx,
                        total_slides=content_total,
                    )
                )
            elif stype == "closing":
                results.append(
                    self.render_closing(
                        slide.get("cta_text", ""),
                        slide.get("account_name", ""),
                    )
                )
        return results
