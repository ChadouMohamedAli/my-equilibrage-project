import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # Database configuration
    DB_HOST = os.getenv("DB_HOST", "192.168.100.250")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "cms")
    DB_USER = os.getenv("DB_USER", "diva")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "diva")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

    # Database configuration 2
    #DB_HOST = os.getenv("DB_HOST", "192.168.10.8")
    #DB_PORT = int(os.getenv("DB_PORT", "3306"))
    #DB_NAME = os.getenv("DB_NAME", "cms")
    #DB_USER = os.getenv("DB_USER", "root")
    #DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    #DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

    # API configuration
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    API_ENDPOINT = os.getenv("API_ENDPOINT", "/solve")
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

    # App configuration
    PAGE_TITLE = "Production Planning System"
    PAGE_ICON = "🏭"


config = Config()