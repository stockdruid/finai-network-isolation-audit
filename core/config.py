from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama (내부 LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"  # finai 통합: 로컬 설치된 모델 (원본 A: bllossom)

    # 외부 LLM (위반 시뮬레이션용 mock 서버)
    external_llm_url: str = "http://localhost:9999/v1/chat/completions"
    external_llm_api_key: str = "sk-mock-key"

    # DB (finai 통합: 하나의 DB에 A의 users + 우리 chatbot_logs·컴플라이언스 매핑 공존)
    database_url: str = "postgresql+asyncpg://finai:finai@localhost:5432/finai"

    # RAG
    chroma_path: str = "./data/chroma"
    embedding_model: str = "jhgan/ko-sroberta-multitask"

    # 외부 API key
    finlife_api_key: str = ""
    ecos_api_key: str = ""

    # 로깅
    log_level: str = "INFO"
    log_file_path: str = "./logs/chatbot.jsonl"

    environment: str = "dev"


settings = Settings()
