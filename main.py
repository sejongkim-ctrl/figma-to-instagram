import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from config import Config
from figma_client import FigmaClient
from image_host import ImageHost
from instagram_client import InstagramClient
from token_manager import TokenManager

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/automation.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Figma → Instagram 카드뉴스 자동화"
    )
    parser.add_argument(
        "--node-ids",
        help="Figma 노드 ID (쉼표 구분, .env 오버라이드)",
    )
    parser.add_argument("--caption", help="Instagram 캡션 (.env 오버라이드)")
    parser.add_argument(
        "--schedule",
        help="예약 발행 시간 (ISO 형식, 예: 2026-02-20T10:00:00+09:00)",
    )
    parser.add_argument(
        "--mode",
        choices=["immediate", "scheduled"],
        help="발행 모드",
    )
    parser.add_argument(
        "--list-frames",
        action="store_true",
        help="Figma 파일의 모든 프레임 목록 조회",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="이미지 추출/업로드만 수행, Instagram 발행은 건너뜀",
    )
    parser.add_argument(
        "--setup-token",
        help="단기 토큰을 입력하면 장기 토큰으로 교환하고 관련 정보를 출력합니다",
    )
    return parser.parse_args()


def cmd_setup_token(short_token):
    """토큰 설정 도우미: 단기 토큰 → 장기 토큰, 페이지/IG ID 조회."""
    logger.info("=== 토큰 설정 시작 ===")

    result = TokenManager.exchange_for_long_lived(short_token)
    long_token = result["access_token"]
    expires_in = result["expires_in"]
    expiry_date = datetime.now() + timedelta(seconds=expires_in)

    logger.info(f"장기 토큰: {long_token[:20]}...{long_token[-10:]}")
    logger.info(f"만료일: {expiry_date.strftime('%Y-%m-%d')}")

    pages = TokenManager.get_page_access_token(long_token)
    if not pages:
        logger.error("연결된 Facebook 페이지가 없습니다.")
        return

    for page in pages:
        logger.info(f"\n--- 페이지: {page['name']} ---")
        logger.info(f"Page ID: {page['id']}")
        page_token = page["access_token"]
        logger.info(f"Page Token: {page_token[:20]}...")

        try:
            ig_id = TokenManager.get_ig_user_id(page["id"], page_token)
            logger.info(f"\n.env에 아래 값을 설정하세요:")
            logger.info(f"  INSTAGRAM_USER_ID={ig_id}")
            logger.info(f"  INSTAGRAM_ACCESS_TOKEN={page_token}")
            logger.info(f"  INSTAGRAM_TOKEN_EXPIRY={expiry_date.strftime('%Y-%m-%d')}")
        except KeyError:
            logger.warning(
                f"  이 페이지에 연결된 Instagram Business 계정이 없습니다."
            )


def cmd_list_frames():
    """Figma 파일의 프레임 목록을 출력합니다."""
    figma = FigmaClient()
    frames = figma.get_file_frames()
    if not frames:
        logger.info("프레임이 없습니다.")
        return
    logger.info(f"총 {len(frames)}개 프레임:")
    for f in frames:
        print(f"  Page: {f['page']} | Frame: {f['name']} | ID: {f['id']}")


def cmd_publish(args):
    """메인 워크플로우: Figma → imgbb → Instagram."""
    node_ids = (
        [n.strip() for n in args.node_ids.split(",")]
        if args.node_ids
        else Config.FIGMA_NODE_IDS
    )
    caption = args.caption or Config.DEFAULT_CAPTION
    mode = args.mode or Config.PUBLISH_MODE

    # 예약 발행 시간 검증
    scheduled_time = None
    if mode == "scheduled":
        time_str = args.schedule or Config.SCHEDULED_TIME
        if not time_str:
            logger.error("예약 모드에는 --schedule 또는 .env의 SCHEDULED_TIME이 필요합니다")
            sys.exit(1)
        scheduled_time = datetime.fromisoformat(time_str)
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if not (now + timedelta(minutes=10) <= scheduled_time <= now + timedelta(days=75)):
            logger.error("예약 시간은 현재로부터 10분~75일 사이여야 합니다")
            sys.exit(1)

    if not node_ids or not node_ids[0]:
        logger.error("Figma 노드 ID가 지정되지 않았습니다. --node-ids 또는 .env를 확인하세요")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("Figma → Instagram 카드뉴스 자동화 시작")
    logger.info(f"  노드: {node_ids}")
    logger.info(f"  모드: {mode}")
    if scheduled_time:
        logger.info(f"  예약 시간: {scheduled_time.isoformat()}")
    logger.info("=" * 50)

    # Step 1: Figma에서 이미지 export
    logger.info("\n[1/4] Figma에서 이미지 export 중...")
    figma = FigmaClient()
    image_urls = figma.export_images(node_ids, fmt="png", scale=2)
    logger.info(f"  {len(image_urls)}개 이미지 URL 획득")

    # Step 2: 로컬 다운로드
    logger.info("\n[2/4] 이미지 다운로드 중...")
    local_files = figma.download_images(image_urls)
    logger.info(f"  {len(local_files)}개 파일 다운로드 완료")

    # Step 3: imgbb 업로드
    logger.info("\n[3/4] imgbb에 업로드 중...")
    host = ImageHost()
    public_urls = host.upload_batch(local_files, expiration=86400)
    logger.info(f"  {len(public_urls)}개 공개 URL 획득")

    if args.dry_run:
        logger.info("\n[드라이런] Instagram 발행을 건너뜁니다.")
        logger.info("공개 URL 목록:")
        for i, url in enumerate(public_urls, 1):
            logger.info(f"  [{i}] {url}")
        return

    # Step 4: Instagram 캐러셀 발행
    logger.info("\n[4/4] Instagram 캐러셀 발행 중...")
    ig = InstagramClient()

    try:
        limits = ig.check_publishing_limit()
        logger.info(f"  발행 한도: {limits}")
    except Exception as e:
        logger.warning(f"  발행 한도 확인 실패 (무시): {e}")

    result = ig.publish_carousel(public_urls, caption, scheduled_time)
    logger.info(f"\n결과: {result}")
    logger.info("자동화 완료!")


def main():
    args = parse_args()

    # 토큰 만료 체크
    if TokenManager.is_token_expiring_soon():
        logger.warning(
            "Instagram 토큰이 곧 만료됩니다. --setup-token으로 갱신하세요."
        )

    if args.setup_token:
        cmd_setup_token(args.setup_token)
    elif args.list_frames:
        cmd_list_frames()
    else:
        cmd_publish(args)


if __name__ == "__main__":
    main()
