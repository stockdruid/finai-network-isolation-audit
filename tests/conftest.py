"""pytest fixtures — 추후 보강."""
import pytest


@pytest.fixture
def sample_log_payload() -> dict:
    return {
        "request_id": "00000000-0000-0000-0000-000000000001",
        "mode": "internal",
        "user_input": "예금 상품 추천",
        "model_name": "EEVE-Korean-10.8B-v1.0",
    }
