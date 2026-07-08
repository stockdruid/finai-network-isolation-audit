"""data/*_seed.json을 읽어서 Chroma에 적재.

실행: PYTHONPATH=. uv run python scripts/seed_chroma.py
"""

import json
from pathlib import Path

from rag.ingest import ingest

DATA_DIR = Path(__file__).parent.parent / "data"
PRODUCTS_PATH = DATA_DIR / "products_seed.json"
CUSTOMERS_PATH = DATA_DIR / "customers_seed.json"


def format_product(item: dict) -> str:
    lines = [f"[{item['category']}] {item.get('bank') or item.get('card_company')} - {item['product_name']}"]
    if "interest_rate" in item:
        lines.append(f"금리: 연 {item['interest_rate']}%")
    if "interest_rate_min" in item:
        lines.append(f"금리: 연 {item['interest_rate_min']}~{item['interest_rate_max']}%")
    if "term_months" in item:
        lines.append(f"기간: {item['term_months']}개월")
    if "min_amount" in item:
        lines.append(f"최소 가입금액: {item['min_amount']:,}원")
    if "min_monthly" in item:
        lines.append(f"최소 월 납입금: {item['min_monthly']:,}원")
    if "credit_limit" in item:
        lines.append(f"최대 한도: {item['credit_limit']:,}원")
    if "annual_fee" in item:
        lines.append(f"연회비: {item['annual_fee']:,}원")
    lines.append(f"설명: {item['description']}")
    return "\n".join(lines)


def format_customer(item: dict) -> str:
    lines = [
        f"[{item['category']}] {item['name']}",
        f"나이: {item['age']}세 / 직업: {item['job']}",
        f"연락처: {item['phone']} / 이메일: {item['email']}",
        f"연소득: {item['annual_income']:,}원 / 신용점수: {item['credit_score']}점",
        f"관심 상품: {', '.join(item['preferred_products'])}",
        f"메모: {item['description']}",
    ]
    return "\n".join(lines)


def load_products():
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return [
        {
            "id": it["id"],
            "document": format_product(it),
            "metadata": {
                "category": it["category"],
                "source": "product_seed_manual",
                "bank_or_company": it.get("bank") or it.get("card_company") or "",
            },
        }
        for it in items
    ]


def load_customers():
    with open(CUSTOMERS_PATH, encoding="utf-8") as f:
        items = json.load(f)
    return [
        {
            "id": it["id"],
            "document": format_customer(it),
            "metadata": {
                "category": it["category"],
                # source가 customer_persona면 EV-002 위반 시나리오 표시
                "source": "customer_persona",
                "customer_name": it["name"],
            },
        }
        for it in items
    ]


def main():
    items = load_products() + load_customers()
    n = ingest(items)
    print(f"ingested {n} documents (products + customer personas)")


if __name__ == "__main__":
    main()
