"""Nemotron-Personas-Korea N개 sampling → JSON 저장.

Usage:
    python scripts/sample_personas.py --n 50 --out data/personas_sample.json

streaming 모드로 첫 N개를 가져옴 (결정성 보장). 무작위 샘플링이 필요하면
HF datasets의 `.shuffle(buffer_size=N*10)` 추가.

라이선스: NVIDIA HF 페이지 확인 필수.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from datasets import load_dataset


def parse_list_field(value: str) -> list[str]:
    """`skills_and_expertise_list` 같이 문자열로 직렬화된 list 필드 파싱."""
    if not value:
        return []
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []


def sample(n: int, out: Path) -> None:
    ds = load_dataset("nvidia/Nemotron-Personas-Korea", split="train", streaming=True)
    rows: list[dict] = []
    for i, row in enumerate(ds):
        # 리스트 필드 파싱하여 사용 편의 향상
        row["skills_and_expertise_list"] = parse_list_field(row.get("skills_and_expertise_list", ""))
        row["hobbies_and_interests_list"] = parse_list_field(row.get("hobbies_and_interests_list", ""))
        rows.append(row)
        if len(rows) >= n:
            break

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"saved {len(rows)} personas to {out}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50, help="샘플 수")
    parser.add_argument("--out", type=Path, default=Path("data/personas_sample.json"))
    args = parser.parse_args()
    sample(args.n, args.out)


if __name__ == "__main__":
    main()
