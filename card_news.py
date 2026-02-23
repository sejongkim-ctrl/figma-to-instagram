"""카드뉴스 이미지 생성기 — v4 Photo-based design."""
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── 템플릿 정의 ───────────────────────────────────────────

TEMPLATES = {
    "깔끔한 화이트": {
        "overlay_color": (0, 0, 0),
        "overlay_alpha": 0.45,
        "text_white": True,
        "card_bg": "#FFFFFF",
        "accent": "#3D7DD9",
        "heading_text": "#1A1A1A",
        "body_text": "#333333",
        "muted": "#999999",
        "item_bg": "#F2F7FF",
        "item_border": "#3D7DD9",
    },
    "다크 프리미엄": {
        "overlay_color": (10, 10, 20),
        "overlay_alpha": 0.55,
        "text_white": True,
        "card_bg": "#1A1A2E",
        "accent": "#E94560",
        "heading_text": "#FFFFFF",
        "body_text": "#E0E0F0",
        "muted": "#666680",
        "item_bg": "#22223A",
        "item_border": "#E94560",
    },
    "수壽 브랜드": {
        "overlay_color": (30, 15, 5),
        "overlay_alpha": 0.50,
        "text_white": True,
        "card_bg": "#FFFBF5",
        "accent": "#C4956A",
        "heading_text": "#2D1810",
        "body_text": "#4A3728",
        "muted": "#B0A090",
        "item_bg": "#F5EDE3",
        "item_border": "#C4956A",
    },
    "건강 그린": {
        "overlay_color": (10, 30, 20),
        "overlay_alpha": 0.50,
        "text_white": True,
        "card_bg": "#FFFFFF",
        "accent": "#40916C",
        "heading_text": "#1B4332",
        "body_text": "#2D5A42",
        "muted": "#88B0A0",
        "item_bg": "#E8F5EE",
        "item_border": "#40916C",
    },
}

# ── 폰트 ──────────────────────────────────────────────────

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_PATHS = {
    "bold": [
        os.path.expanduser("~/Library/Fonts/Pretendard-Bold.otf"),
        os.path.join(_FONT_DIR, "Pretendard-Bold.otf"),
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ],
    "semibold": [
        os.path.expanduser("~/Library/Fonts/Pretendard-SemiBold.otf"),
        os.path.join(_FONT_DIR, "Pretendard-SemiBold.otf"),
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


# ── 유틸리티 ──────────────────────────────────────────────


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def _fit_cover(photo, w, h):
    """사진을 w×h 크기에 꽉 차게 crop + resize (cover fit)."""
    pw, ph = photo.size
    target_ratio = w / h
    photo_ratio = pw / ph
    if photo_ratio > target_ratio:
        new_h = ph
        new_w = int(ph * target_ratio)
        left = (pw - new_w) // 2
        photo = photo.crop((left, 0, left + new_w, ph))
    else:
        new_w = pw
        new_h = int(pw / target_ratio)
        top = (ph - new_h) // 2
        photo = photo.crop((0, top, pw, top + new_h))
    return photo.resize((w, h), Image.LANCZOS)


def _gradient_overlay(img, color, alpha_top, alpha_bottom):
    """상단→하단 그라디언트 오버레이."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    r, g, b = color
    for y in range(h):
        t = y / max(h - 1, 1)
        a = int(alpha_top + (alpha_bottom - alpha_top) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b, a))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _solid_overlay(img, color, alpha):
    """단색 반투명 오버레이."""
    overlay = Image.new("RGBA", img.size, color + (int(alpha * 255),))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _open_image(source):
    """bytes 또는 PIL Image를 PIL Image로 변환."""
    if source is None:
        return None
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGB")
    return None


# ── 렌더러 ────────────────────────────────────────────────


class CardNewsRenderer:
    """사진 배경 기반 카드뉴스 생성기."""

    def __init__(self, template_name, size=(1080, 1080)):
        if template_name not in TEMPLATES:
            raise ValueError(f"알 수 없는 템플릿: {template_name}")
        self.t = TEMPLATES[template_name]
        self.w, self.h = size

    def _wrap(self, draw, text, font, max_w):
        lines = []
        for para in text.split("\n"):
            if not para.strip():
                lines.append("")
                continue
            words = para.split()
            if not words:
                lines.append("")
                continue
            cur = words[0]
            for w in words[1:]:
                test = cur + " " + w
                if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
        return lines

    def _tw(self, d, t, f):
        b = d.textbbox((0, 0), t, font=f)
        return b[2] - b[0]

    def _th(self, d, t, f):
        b = d.textbbox((0, 0), t, font=f)
        return b[3] - b[1]

    def _to_bytes(self, img):
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _draw_text_shadow(self, draw, xy, text, font, fill, shadow_color=(0, 0, 0), offset=2):
        """텍스트에 그림자 효과."""
        x, y = xy
        # 그림자
        draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
        # 본문
        draw.text((x, y), text, font=font, fill=fill)

    # ── 표지: 전체 사진 배경 + 그라디언트 오버레이 + 텍스트 ──

    def render_cover(self, title, subtitle="", bg_image=None):
        photo = _open_image(bg_image)

        if photo:
            img = _fit_cover(photo, self.w, self.h)
            # 상단 살짝 어둡게 + 하단 많이 어둡게 (텍스트 가독성)
            oc = self.t["overlay_color"]
            img = _gradient_overlay(img, oc, 40, 200)
        else:
            # 사진 없으면 단색 그라디언트 폴백
            img = Image.new("RGB", (self.w, self.h), _hex("#1A1A2E"))
            draw_tmp = ImageDraw.Draw(img)
            for y in range(self.h):
                t = y / max(self.h - 1, 1)
                r = int(30 + 20 * t)
                g = int(30 + 20 * t)
                b = int(50 + 30 * t)
                draw_tmp.line([(0, y), (self.w, y)], fill=(r, g, b))

        draw = ImageDraw.Draw(img)
        pad = 80

        font_t = _load_font("bold", 72)
        font_s = _load_font("medium", 32)
        max_w = self.w - pad * 2

        lines_t = self._wrap(draw, title, font_t, max_w)
        lines_s = self._wrap(draw, subtitle, font_s, max_w) if subtitle else []
        lh_t = self._th(draw, "가", font_t)
        lh_s = self._th(draw, "가", font_s) if lines_s else 0

        spacing_t = 16
        block_t = lh_t * len(lines_t) + spacing_t * max(0, len(lines_t) - 1)
        block_s = (lh_s * len(lines_s) + 8 * max(0, len(lines_s) - 1)) if lines_s else 0
        divider_h = 50 if lines_s else 0
        total = block_t + divider_h + block_s

        # 텍스트를 하단 1/3 영역에 배치
        y = self.h - pad - total - 60

        # 반투명 배경 패널
        panel_pad = 30
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(
            [pad - panel_pad, y - panel_pad,
             self.w - pad + panel_pad, y + total + panel_pad + 20],
            radius=20,
            fill=(0, 0, 0, 60),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 제목
        white = (255, 255, 255)
        for ln in lines_t:
            lw = self._tw(draw, ln, font_t)
            self._draw_text_shadow(
                draw, ((self.w - lw) // 2, y), ln, font_t, white,
                shadow_color=(0, 0, 0), offset=3,
            )
            y += lh_t + spacing_t

        # 구분선
        if lines_s:
            y += 8
            cx = self.w // 2
            sub_c = (255, 255, 255, 120)
            # 액센트 라인
            accent_c = _hex(self.t["accent"])
            draw.line([(cx - 60, y), (cx + 60, y)], fill=accent_c, width=3)
            y += 22

            for ln in lines_s:
                lw = self._tw(draw, ln, font_s)
                draw.text(
                    ((self.w - lw) // 2, y), ln,
                    font=font_s, fill=(220, 220, 220),
                )
                y += lh_s + 8

        return self._to_bytes(img)

    # ── 본문: 상단 사진 + 하단 텍스트 카드 ──

    def render_content(self, heading, body, slide_num=None, total_slides=None, bg_image=None):
        photo = _open_image(bg_image)

        img = Image.new("RGB", (self.w, self.h), _hex(self.t["card_bg"]))
        draw = ImageDraw.Draw(img)

        # 사진 영역 비율 (사진 있으면 상단 38%, 없으면 헤딩 바만)
        if photo:
            photo_h = int(self.h * 0.38)
            photo_img = _fit_cover(photo, self.w, photo_h)
            # 사진 하단에 그라디언트 페이드
            oc = self.t["overlay_color"]
            photo_img = _gradient_overlay(photo_img, oc, 0, 160)
            img.paste(photo_img, (0, 0))

            # 사진 위에 소제목 오버레이
            draw = ImageDraw.Draw(img)
            font_h = _load_font("bold", 42)
            h_lines = self._wrap(draw, heading.strip(), font_h, self.w - 140)
            lh_h = self._th(draw, "가", font_h)

            # 넘버 뱃지
            badge_x = 70
            badge_y = photo_h - 70
            if slide_num is not None:
                # 액센트 컬러 뱃지
                accent = _hex(self.t["accent"])
                draw.ellipse(
                    [badge_x - 24, badge_y - 24, badge_x + 24, badge_y + 24],
                    fill=accent,
                )
                font_n = _load_font("bold", 26)
                nt = str(slide_num)
                draw.text(
                    (badge_x - self._tw(draw, nt, font_n) // 2,
                     badge_y - self._th(draw, nt, font_n) // 2),
                    nt, font=font_n, fill=(255, 255, 255),
                )
                text_x = badge_x + 40
            else:
                text_x = 70

            # 소제목 (사진 하단에 흰색)
            h_y = badge_y - lh_h // 2
            for ln in h_lines:
                self._draw_text_shadow(
                    draw, (text_x, h_y), ln, font_h, (255, 255, 255),
                    shadow_color=(0, 0, 0), offset=2,
                )
                h_y += lh_h + 8
                text_x = 70  # 두 번째 줄부터는 왼쪽 정렬

            text_area_top = photo_h + 10
        else:
            # 사진 없으면 헤딩 바
            font_h = _load_font("bold", 38)
            h_lines = self._wrap(draw, heading.strip(), font_h, self.w - 180)
            lh_h = self._th(draw, "가", font_h)
            h_block = lh_h * len(h_lines) + 8 * max(0, len(h_lines) - 1)
            bar_h = h_block + 36

            draw.rounded_rectangle(
                [20, 50, self.w - 20, 50 + bar_h],
                radius=14,
                fill=_hex(self.t["accent"]),
            )
            if slide_num is not None:
                draw.ellipse([50 - 22, 50 + bar_h // 2 - 22, 50 + 22, 50 + bar_h // 2 + 22], fill=(255, 255, 255))
                font_n = _load_font("bold", 24)
                nt = str(slide_num)
                draw.text(
                    (50 - self._tw(draw, nt, font_n) // 2,
                     50 + bar_h // 2 - self._th(draw, nt, font_n) // 2),
                    nt, font=font_n, fill=_hex(self.t["accent"]),
                )
                tx = 86
            else:
                tx = 50

            hy = 50 + 18
            for ln in h_lines:
                draw.text((tx, hy), ln, font=font_h, fill=(255, 255, 255))
                hy += lh_h + 8

            text_area_top = 50 + bar_h + 20

        # ── 본문 항목 카드 ──
        font_body = _load_font("medium", 30)
        font_desc = _load_font("regular", 24)
        lh_body = self._th(draw, "가", font_body)
        lh_desc = self._th(draw, "가", font_desc)

        # 불렛 항목 파싱
        items = []
        current_item = None
        for line in body.strip().split("\n"):
            line = line.strip()
            if not line:
                if current_item:
                    items.append(current_item)
                    current_item = None
                continue
            is_bullet = False
            text = line
            if line.startswith(("-", "•", "·")):
                is_bullet = True
                text = line[1:].strip()
            elif len(line) > 2 and line[0].isdigit() and line[1] in (".", ")"):
                is_bullet = True
                text = line[2:].strip()
            if is_bullet:
                if current_item:
                    items.append(current_item)
                current_item = {"title": text, "desc": ""}
            else:
                if current_item:
                    current_item["desc"] += (" " if current_item["desc"] else "") + text
                else:
                    items.append({"title": text, "desc": ""})
        if current_item:
            items.append(current_item)
        if not items:
            items = [{"title": body.strip(), "desc": ""}]

        pad_x = 50
        item_max_w = self.w - pad_x * 2 - 30
        bottom_pad = 60
        available_h = self.h - text_area_top - bottom_pad
        item_gap = 12
        per_item = max(55, (available_h - item_gap * max(0, len(items) - 1)) // max(len(items), 1))

        y = text_area_top + 10

        for item in items:
            if y + 50 > self.h - bottom_pad:
                break

            card_h = per_item
            # 아이템 카드 배경
            draw.rounded_rectangle(
                [pad_x, y, self.w - pad_x, y + card_h],
                radius=12,
                fill=_hex(self.t["item_bg"]),
            )
            # 좌측 액센트 바
            draw.rounded_rectangle(
                [pad_x, y + 4, pad_x + 5, y + card_h - 4],
                radius=2,
                fill=_hex(self.t["item_border"]),
            )

            tx = pad_x + 22
            ty = y + 14
            tlines = self._wrap(draw, item["title"], font_body, item_max_w)
            for tl in tlines:
                if ty + lh_body > y + card_h - 8:
                    break
                draw.text((tx, ty), tl, font=font_body, fill=_hex(self.t["heading_text"]))
                ty += lh_body + 4

            if item["desc"]:
                ty += 4
                dlines = self._wrap(draw, item["desc"], font_desc, item_max_w)
                for dl in dlines:
                    if ty + lh_desc > y + card_h - 8:
                        break
                    draw.text((tx, ty), dl, font=font_desc, fill=_hex(self.t["body_text"]))
                    ty += lh_desc + 3

            y += card_h + item_gap

        # 페이지 번호
        if slide_num is not None and total_slides is not None:
            font_p = _load_font("regular", 22)
            pt = f"{slide_num} / {total_slides}"
            pw = self._tw(draw, pt, font_p)
            draw.text(
                (self.w - pad_x - pw, self.h - 40),
                pt, font=font_p, fill=_hex(self.t["muted"]),
            )

        return self._to_bytes(img)

    # ── 마무리: 사진 배경 + 풀 오버레이 + CTA ──

    def render_closing(self, cta_text, account_name="", bg_image=None):
        photo = _open_image(bg_image)

        if photo:
            img = _fit_cover(photo, self.w, self.h)
            # 블러 + 어두운 오버레이
            img = img.filter(ImageFilter.GaussianBlur(radius=6))
            oc = self.t["overlay_color"]
            img = _solid_overlay(img, oc, self.t["overlay_alpha"] + 0.1)
        else:
            # 폴백: 그라디언트
            img = Image.new("RGB", (self.w, self.h))
            d = ImageDraw.Draw(img)
            accent = _hex(self.t["accent"])
            darker = tuple(max(0, c - 40) for c in accent)
            for y in range(self.h):
                t = y / max(self.h - 1, 1)
                c = tuple(int(accent[i] + (darker[i] - accent[i]) * t) for i in range(3))
                d.line([(0, y), (self.w, y)], fill=c)

        draw = ImageDraw.Draw(img)
        pad = 100

        font_cta = _load_font("serif", 48)
        font_acc = _load_font("medium", 30)

        lines_cta = self._wrap(draw, cta_text, font_cta, self.w - pad * 2)
        lh_cta = self._th(draw, "가", font_cta)
        lh_acc = self._th(draw, "가", font_acc) if account_name else 0

        block_cta = lh_cta * len(lines_cta) + 14 * max(0, len(lines_cta) - 1)
        gap = 60 if account_name else 0
        total = block_cta + gap + lh_acc
        y = (self.h - total) // 2

        # 반투명 패널
        panel_pad = 30
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(
            [pad - panel_pad, y - panel_pad,
             self.w - pad + panel_pad, y + total + panel_pad],
            radius=20,
            fill=(0, 0, 0, 50),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        for ln in lines_cta:
            lw = self._tw(draw, ln, font_cta)
            self._draw_text_shadow(
                draw, ((self.w - lw) // 2, y), ln, font_cta, (255, 255, 255),
                shadow_color=(0, 0, 0), offset=2,
            )
            y += lh_cta + 14

        if account_name:
            y += 12
            cx = self.w // 2
            accent_c = _hex(self.t["accent"])
            draw.line([(cx - 50, y), (cx + 50, y)], fill=accent_c, width=2)
            y += 20
            aw = self._tw(draw, account_name, font_acc)
            draw.text(
                ((self.w - aw) // 2, y), account_name,
                font=font_acc, fill=(200, 200, 200),
            )

        return self._to_bytes(img)

    # ── 전체 렌더 ──

    def render_all(self, slides_data):
        """모든 슬라이드를 렌더링.

        slides_data 예시:
        [
            {"type": "cover", "title": "...", "subtitle": "...", "bg_image": bytes|PIL|None},
            {"type": "content", "heading": "...", "body": "...", "bg_image": ...},
            {"type": "closing", "cta_text": "...", "account_name": "...", "bg_image": ...},
        ]
        """
        results = []
        content_idx = 0
        content_total = sum(1 for s in slides_data if s["type"] == "content")
        for slide in slides_data:
            st = slide["type"]
            bg = slide.get("bg_image")
            if st == "cover":
                results.append(self.render_cover(
                    slide.get("title", ""), slide.get("subtitle", ""), bg_image=bg,
                ))
            elif st == "content":
                content_idx += 1
                results.append(self.render_content(
                    slide.get("heading", ""), slide.get("body", ""),
                    slide_num=content_idx, total_slides=content_total, bg_image=bg,
                ))
            elif st == "closing":
                results.append(self.render_closing(
                    slide.get("cta_text", ""), slide.get("account_name", ""), bg_image=bg,
                ))
        return results
