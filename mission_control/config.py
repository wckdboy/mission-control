from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./mission_control.db"
    operator_username: str = "doomerius"
    operator_password: str = "change-me"
    operator_password_hash: str = ""  # optional: sha256 hex; wins over plaintext
    session_secret: str = "dev-session-secret"
    public_base_url: str = "http://localhost:8000"
    agent_seeds: str = ""
    data_dir: str = "./data"
    frontend_dist: str = "./web/dist"
    cookie_secure: bool = False
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        env_prefix = ""


settings = Settings()
