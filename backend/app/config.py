import os
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _db_password() -> str:
    """DB 암호는 SSM Parameter Store(SecureString)에서 조회한다. 로컬 개발만 DB_PASSWORD 허용."""
    param = os.getenv("DB_PASSWORD_SSM_PARAM")
    if param:
        import boto3

        ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
        return ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
    return os.getenv("DB_PASSWORD", "")


class Settings:
    def __init__(self) -> None:
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "coupon")
        self.db_user = os.getenv("DB_USER", "coupon")
        self.db_password = _db_password()
        self.db_sslmode = os.getenv("DB_SSLMODE", "prefer")
        self.db_pool_max = int(os.getenv("DB_POOL_MAX", "20"))

        self.cache_enabled = _bool("CACHE_ENABLED", True)
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_tls = _bool("REDIS_TLS", False)
        self.cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "3"))

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} sslmode={self.db_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
