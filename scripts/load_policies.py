"""정책 YAML → policy_mappings 테이블 로드.

Usage:
    python scripts/load_policies.py                    # upsert (code 기준)
    python scripts/load_policies.py --reset            # 기존 삭제 후 재로드
    python scripts/load_policies.py --file other.yaml  # 커스텀 파일
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml
from sqlalchemy import delete, select

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import PolicyMapping
from db.session import SessionLocal, engine

DEFAULT_YAML = Path(__file__).resolve().parent.parent / "data" / "policies.yaml"


async def load(yaml_path: Path, reset: bool) -> None:
    with open(yaml_path, encoding="utf-8") as f:
        policies = yaml.safe_load(f)

    if not policies:
        print("[error] YAML 파일이 비어있거나 파싱 실패")
        return

    async with SessionLocal() as session:
        if reset:
            await session.execute(delete(PolicyMapping))
            await session.commit()
            print("[reset] policy_mappings 테이블 초기화")

        created, updated = 0, 0
        for p in policies:
            existing = await session.execute(
                select(PolicyMapping).where(PolicyMapping.code == p["code"])
            )
            row = existing.scalar_one_or_none()

            if row is None:
                session.add(PolicyMapping(
                    category=p["category"],
                    code=p["code"],
                    title=p["title"],
                    description=p.get("description"),
                    severity_weight=p.get("severity_weight", 5.0),
                    related_rules=p.get("related_rules", []),
                ))
                created += 1
            else:
                row.category = p["category"]
                row.title = p["title"]
                row.description = p.get("description")
                row.severity_weight = p.get("severity_weight", 5.0)
                row.related_rules = p.get("related_rules", [])
                updated += 1

        await session.commit()
        print(f"[done] {created}건 생성, {updated}건 업데이트 (총 {len(policies)}건)")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="정책 YAML → DB 로드")
    parser.add_argument("--file", type=Path, default=DEFAULT_YAML, help="YAML 파일 경로")
    parser.add_argument("--reset", action="store_true", help="기존 데이터 삭제 후 재로드")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"[error] 파일 없음: {args.file}")
        return

    asyncio.run(load(args.file, args.reset))


if __name__ == "__main__":
    main()
