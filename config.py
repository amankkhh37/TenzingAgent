"""
Configuration management for Tenzing Growth Agent
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
EXPORTS_DIR = PROJECT_ROOT / "exports"

# Ensure directories exist
for directory in [DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, EXPORTS_DIR]:
    directory.mkdir(exist_ok=True)

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "travel_crm.db"))

# Facebook Configuration
FACEBOOK_PROFILE_PATH = os.getenv("FACEBOOK_PROFILE_PATH", str(PROJECT_ROOT / ".facebook_session"))
FACEBOOK_HEADLESS = os.getenv("FACEBOOK_HEADLESS", "false").lower() == "true"

# Ollama Configuration
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()  # auto, ollama, azure

# Azure OpenAI / Foundry Responses API
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# Scanner Configuration
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "30"))  # 5 minutes
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", "10"))
GROUP_URLS = os.getenv("GROUP_URLS", "").split(",") if os.getenv("GROUP_URLS") else []
SCAN_LOGIN_WAIT_SECONDS = int(os.getenv("SCAN_LOGIN_WAIT_SECONDS", "60"))
REQUIRE_LOGIN_BEFORE_SCAN = os.getenv("REQUIRE_LOGIN_BEFORE_SCAN", "true").lower() == "true"

# Comment Worker Configuration
COMMENT_CHECK_INTERVAL = int(os.getenv("COMMENT_CHECK_INTERVAL", "10"))  # 10 seconds
COMMENT_RETRY_ATTEMPTS = int(os.getenv("COMMENT_RETRY_ATTEMPTS", "3"))
COMMENT_RETRY_DELAY = int(os.getenv("COMMENT_RETRY_DELAY", "5"))

# Content Generator Configuration
CONTENT_GENERATION_HOUR = int(os.getenv("CONTENT_GENERATION_HOUR", "9"))  # 9 AM

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Lead Scoring Thresholds
LEAD_SCORE_HIGH = int(os.getenv("LEAD_SCORE_HIGH", "8"))
LEAD_SCORE_MEDIUM = int(os.getenv("LEAD_SCORE_MEDIUM", "5"))
LEAD_SCORE_LOW = int(os.getenv("LEAD_SCORE_LOW", "0"))

# UI Configuration
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8501"))
DASHBOARD_THEME = os.getenv("DASHBOARD_THEME", "light")

# Business Configuration
BUSINESS_NAME = "Sikkim Tours & Cabs"
BUSINESS_LOCATIONS = ["Sikkim", "Gangtok", "Darjeeling", "NJP"]
