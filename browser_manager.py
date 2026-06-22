"""
Shared Playwright browser manager.
Ensures a single persistent Facebook browser context is reused.
"""
import threading
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page
from config import FACEBOOK_PROFILE_PATH
from logger import app_logger


class BrowserManager:
    _lock = threading.Lock()
    _playwright: Optional[Playwright] = None
    _context: Optional[BrowserContext] = None

    @classmethod
    def _is_context_alive(cls) -> bool:
        try:
            return cls._context is not None and len(cls._context.pages) >= 0
        except Exception:
            return False

    @classmethod
    def get_or_create_context(cls, headless: bool = False) -> BrowserContext:
        with cls._lock:
            if cls._is_context_alive():
                return cls._context

            if cls._playwright is None:
                cls._playwright = sync_playwright().start()

            app_logger.info(
                "Creating shared Facebook browser context (headless=%s, profile=%s)",
                headless,
                FACEBOOK_PROFILE_PATH,
            )
            cls._context = cls._playwright.chromium.launch_persistent_context(
                FACEBOOK_PROFILE_PATH,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            return cls._context

    @classmethod
    def get_or_create_page(cls, headless: bool = False) -> Page:
        context = cls.get_or_create_context(headless=headless)
        pages = context.pages
        if pages:
            return pages[0]
        return context.new_page()

    @classmethod
    def open_login_tab(cls) -> None:
        page = cls.get_or_create_page(headless=False)
        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")

    @classmethod
    def context_status(cls) -> bool:
        with cls._lock:
            return cls._is_context_alive()
