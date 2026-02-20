import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import streamlit as st

# ── Streamlit Cloud secrets → 환경 변수 브릿지 ────────────
# st.secrets (Cloud) 에 [api] 섹션이 있으면 환경 변수로 주입하여
# config.py 가 동일하게 동작하도록 합니다.
try:
    if "api" in st.secrets:
        for key, value in st.secrets["api"].items():
            os.environ.setdefault(key, str(value))
except Exception:
    pass

# 로컬 개발용 .env 폴백
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from figma_client import FigmaClient
from image_host import ImageHost
from instagram_client import InstagramClient

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")
IS_CLOUD = "api" in st.secrets if hasattr(st, "secrets") else False


# ── 계정 관리 ──────────────────────────────────────────────


def load_accounts():
    # 1) 로컬 accounts.json
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("accounts", [])
    # 2) Streamlit Cloud secrets [[accounts]]
    try:
        if "accounts" in st.secrets:
            return [dict(a) for a in st.secrets["accounts"]]
    except Exception:
        pass
    return []


def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts}, f, ensure_ascii=False, indent=2)


# ── 프레임 그룹핑 ─────────────────────────────────────────


def group_frames_by_date(frames):
    """프레임 이름에서 날짜를 추출하여 그룹핑합니다.
    예: '250213-1' → 그룹 '250213'
    """
    groups = defaultdict(list)
    ungrouped = []
    for f in frames:
        match = re.match(r"^(\d{6})-(\d+)$", f["name"])
        if match:
            date_key = match.group(1)
            order = int(match.group(2))
            groups[date_key].append({**f, "_order": order})
        else:
            ungrouped.append(f)

    # 각 그룹 내에서 순서 정렬
    for key in groups:
        groups[key].sort(key=lambda x: x["_order"])

    return dict(sorted(groups.items(), reverse=True)), ungrouped


# ── 페이지 설정 ───────────────────────────────────────────

st.set_page_config(
    page_title="카드뉴스 → Instagram",
    page_icon="📸",
    layout="wide",
)

st.title("📸 카드뉴스 Instagram 발행")

# ── 사이드바: 계정 & 설정 ─────────────────────────────────

with st.sidebar:
    st.header("설정")

    accounts = load_accounts()

    if not accounts:
        st.warning("등록된 계정이 없습니다.")
    else:
        account_names = [a["name"] for a in accounts]
        selected_name = st.selectbox("Instagram 계정", account_names)
        selected_account = next(a for a in accounts if a["name"] == selected_name)

        # 토큰 만료 경고
        expiry = selected_account.get("token_expiry", "")
        if expiry:
            try:
                exp_date = datetime.fromisoformat(expiry)
                days_left = (exp_date - datetime.now()).days
                if days_left <= 7:
                    st.error(f"⚠️ 토큰 만료 {days_left}일 남음!")
                else:
                    st.caption(f"토큰 만료: {expiry} ({days_left}일 남음)")
            except ValueError:
                pass

    st.divider()

    figma_file_key = st.text_input(
        "Figma 파일 키",
        value=os.getenv("FIGMA_FILE_KEY", ""),
        help="Figma URL에서 /file/ 뒤의 문자열",
    )

    st.divider()

    # 계정 관리
    with st.expander("계정 관리"):
        st.caption("새 계정 추가")
        new_name = st.text_input("계정 이름", key="new_name")
        new_ig_id = st.text_input("Instagram User ID", key="new_ig_id")
        new_token = st.text_input("Access Token", key="new_token", type="password")
        new_expiry = st.text_input("토큰 만료일 (YYYY-MM-DD)", key="new_expiry")

        if st.button("계정 추가"):
            if new_name and new_ig_id and new_token:
                accounts.append(
                    {
                        "name": new_name,
                        "instagram_user_id": new_ig_id,
                        "access_token": new_token,
                        "token_expiry": new_expiry,
                    }
                )
                save_accounts(accounts)
                st.success(f"'{new_name}' 계정이 추가되었습니다.")
                st.rerun()
            else:
                st.error("이름, User ID, Token은 필수입니다.")

        if accounts:
            st.caption("계정 삭제")
            del_name = st.selectbox(
                "삭제할 계정",
                [a["name"] for a in accounts],
                key="del_account",
            )
            if st.button("삭제", type="secondary"):
                accounts = [a for a in accounts if a["name"] != del_name]
                save_accounts(accounts)
                st.success(f"'{del_name}' 계정이 삭제되었습니다.")
                st.rerun()

# ── 메인: Step 1 - 프레임 선택 ────────────────────────────

if not accounts:
    st.info("사이드바에서 Instagram 계정을 먼저 추가해주세요.")
    st.stop()

st.header("Step 1. 프레임 선택")

# 프레임 목록을 Figma에서 가져오되 캐시 활용
if "frames" not in st.session_state:
    st.session_state.frames = None
    st.session_state.frame_groups = None
    st.session_state.ungrouped = None

col_load, col_info = st.columns([1, 3])
with col_load:
    if st.button("🔄 프레임 불러오기", use_container_width=True):
        with st.spinner("Figma에서 프레임 목록을 가져오는 중..."):
            figma = FigmaClient()
            # 인스타그램 v2 페이지의 프레임만 가져오기
            all_frames = figma.get_file_frames(figma_file_key)
            # "인스타그램" 페이지 프레임만 필터
            ig_frames = [
                f for f in all_frames if "인스타그램" in f.get("page", "")
            ]
            if not ig_frames:
                ig_frames = all_frames
            st.session_state.frames = ig_frames
            groups, ungrouped = group_frames_by_date(ig_frames)
            st.session_state.frame_groups = groups
            st.session_state.ungrouped = ungrouped

with col_info:
    if st.session_state.frames:
        st.caption(
            f"총 {len(st.session_state.frames)}개 프레임, "
            f"{len(st.session_state.frame_groups or {})}개 날짜 그룹"
        )

if st.session_state.frame_groups:
    groups = st.session_state.frame_groups

    # 날짜 그룹 선택
    selected_group = st.selectbox(
        "날짜 선택 (최신순)",
        list(groups.keys()),
        format_func=lambda x: f"{x} ({len(groups[x])}장)",
    )

    if selected_group:
        group_frames = groups[selected_group]
        st.caption(f"{selected_group} 시리즈: {len(group_frames)}장")

        # 개별 프레임 체크박스
        selected_frames = []
        cols = st.columns(min(len(group_frames), 5))
        for i, frame in enumerate(group_frames):
            with cols[i % 5]:
                checked = st.checkbox(
                    frame["name"],
                    value=True,
                    key=f"frame_{frame['id']}",
                )
                if checked:
                    selected_frames.append(frame)

        st.info(f"✅ {len(selected_frames)}장 선택됨")

        # 선택된 프레임 ID를 session_state에 저장
        st.session_state.selected_node_ids = [f["id"] for f in selected_frames]

# ── 메인: Step 2 - 미리보기 + 캡션 ───────────────────────

if st.session_state.get("selected_node_ids"):
    st.divider()
    st.header("Step 2. 미리보기 & 캡션")

    node_ids = st.session_state.selected_node_ids

    # 미리보기 이미지 로드
    if st.button("👁️ 미리보기 불러오기"):
        with st.spinner("Figma에서 이미지를 가져오는 중..."):
            figma = FigmaClient()
            image_urls = figma.export_images(node_ids, fmt="png", scale=1)
            # URL 순서를 node_ids 순서에 맞춤
            ordered_urls = []
            for nid in node_ids:
                url = image_urls.get(nid)
                if url:
                    ordered_urls.append(url)
            st.session_state.preview_urls = ordered_urls

    if st.session_state.get("preview_urls"):
        preview_urls = st.session_state.preview_urls
        cols = st.columns(min(len(preview_urls), 5))
        for i, url in enumerate(preview_urls):
            with cols[i % 5]:
                st.image(url, caption=f"{i + 1}장", use_container_width=True)

    # 캡션 입력
    caption = st.text_area(
        "캡션",
        placeholder="게시물 캡션을 입력하세요 (해시태그 포함 가능)",
        height=100,
    )

    # 발행 모드
    publish_mode = st.radio(
        "발행 모드",
        ["즉시 발행", "예약 발행"],
        horizontal=True,
    )

    scheduled_time = None
    if publish_mode == "예약 발행":
        col_date, col_time = st.columns(2)
        with col_date:
            pub_date = st.date_input(
                "발행 날짜",
                value=datetime.now() + timedelta(days=1),
            )
        with col_time:
            pub_time = st.time_input("발행 시간", value=datetime.now().replace(hour=10, minute=0))
        kst = timezone(timedelta(hours=9))
        scheduled_time = datetime.combine(pub_date, pub_time).replace(tzinfo=kst)
        st.caption(f"예약 시간: {scheduled_time.isoformat()}")

    # ── Step 3: 발행 ──────────────────────────────────────

    st.divider()
    st.header("Step 3. 발행")

    col_confirm, col_publish = st.columns([1, 1])
    with col_confirm:
        confirmed = st.checkbox("발행을 확인합니다")
    with col_publish:
        publish_clicked = st.button(
            "🚀 Instagram에 발행하기",
            type="primary",
            disabled=not confirmed,
            use_container_width=True,
        )

    if publish_clicked and confirmed:
        if not caption.strip():
            st.error("캡션을 입력해주세요.")
        elif len(node_ids) < 2:
            st.error("캐러셀은 최소 2장의 이미지가 필요합니다.")
        else:
            progress = st.progress(0)
            status = st.status("발행 진행 중...", expanded=True)

            try:
                # Step 1: Figma export
                status.write("📐 Figma에서 이미지 추출 중...")
                figma = FigmaClient()
                image_urls = figma.export_images(node_ids, fmt="png", scale=2)
                progress.progress(20)

                # Step 2: Download
                status.write("⬇️ 이미지 다운로드 중...")
                local_files = figma.download_images(image_urls)
                # node_ids 순서에 맞춤
                ordered_files = []
                for nid in node_ids:
                    safe = nid.replace(":", "-")
                    path = os.path.join("downloads", f"frame_{safe}.png")
                    if os.path.exists(path):
                        ordered_files.append(path)
                progress.progress(40)

                # Step 3: imgbb upload
                status.write("☁️ 이미지 업로드 중...")
                host = ImageHost()
                public_urls = host.upload_batch(ordered_files, expiration=86400)
                progress.progress(60)

                # Step 4: Instagram publish
                status.write("📸 Instagram에 발행 중...")
                ig = InstagramClient()
                ig.user_id = selected_account["instagram_user_id"]
                ig.access_token = selected_account["access_token"]

                result = ig.publish_carousel(
                    public_urls,
                    caption,
                    scheduled_time,
                )
                progress.progress(100)

                if result["status"] == "published":
                    status.update(label="발행 완료!", state="complete")
                    st.success(
                        f"✅ 발행 성공! Media ID: {result['media_id']}"
                    )
                    st.balloons()
                else:
                    status.update(label="예약 완료!", state="complete")
                    st.success(
                        f"⏰ 예약 완료! Container ID: {result['container_id']}\n\n"
                        f"발행 시간: {scheduled_time.isoformat()}"
                    )

            except Exception as e:
                status.update(label="에러 발생", state="error")
                st.error(f"❌ 발행 실패: {e}")
