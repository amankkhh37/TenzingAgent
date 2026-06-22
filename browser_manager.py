"""
Shared Playwright browser manager.
Ensures a single persistent Facebook browser context is reused.
"""
import threading
import time
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page
from config import FACEBOOK_PROFILE_PATH
from logger import app_logger


class BrowserManager:
    _lock = threading.Lock()
    _playwright: Optional[Playwright] = None
    _context: Optional[BrowserContext] = None
    _login_page: Optional[Page] = None
    _owner_thread_id: Optional[int] = None

    @classmethod
    def _is_context_alive(cls) -> bool:
        try:
            return cls._context is not None and len(cls._context.pages) >= 0
        except Exception:
            return False

    @classmethod
    def get_or_create_context(cls, headless: bool = False) -> BrowserContext:
        with cls._lock:
            current_thread_id = threading.get_ident()
            if cls._context is not None and cls._owner_thread_id != current_thread_id:
                raise RuntimeError(
                    "Shared Facebook browser context was created on a different "
                    "thread. Click 'I have completed Facebook login' to close the "
                    "login browser before starting the scanner."
                )

            if cls._is_context_alive():
                return cls._context

            if cls._playwright is None:
                cls._playwright = sync_playwright().start()

            app_logger.info(
                "Creating shared Facebook browser context (headless=%s, profile=%s)",
                headless,
                FACEBOOK_PROFILE_PATH,
            )
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            # Guard against transient profile lock if another thread/process just opened it.
            last_error = None
            for attempt in range(1, 4):
                try:
                    cls._context = cls._playwright.chromium.launch_persistent_context(
                        FACEBOOK_PROFILE_PATH,
                        headless=headless,
                        args=launch_args,
                    )
                    cls._owner_thread_id = current_thread_id
                    return cls._context
                except Exception as e:
                    last_error = e
                    message = str(e)
                    if "Opening in existing browser session" in message and attempt < 3:
                        app_logger.warning(
                            "Facebook profile is temporarily locked; retrying context launch (%s/3)",
                            attempt,
                        )
                        time.sleep(1)
                        if cls._is_context_alive():
                            return cls._context
                        continue
                    raise

            if last_error:
                raise last_error
            return cls._context

    
    @classmethod
    def get_or_create_page(cls, headless: bool = False) -> Page:

        context = cls.get_or_create_context(headless=headless)

        pages = context.pages

        if pages:
            return pages[-1]

        return context.new_page()

    @classmethod
    def open_login_tab(cls) -> None:

        context = cls.get_or_create_context(headless=False)

        page = context.new_page()

        cls._login_page = page

        page.goto(
            "https://www.facebook.com/login",
            wait_until="domcontentloaded"
        )

        app_logger.info("Facebook login page opened")

    @classmethod
    def close_context(cls) -> None:
        """Close the browser context owned by the current thread."""
        with cls._lock:
            current_thread_id = threading.get_ident()
            if cls._context is None:
                return

            if cls._owner_thread_id != current_thread_id:
                raise RuntimeError(
                    "Cannot close Facebook browser context from a different thread. "
                    "Close the visible login browser window, then start the scanner."
                )

            try:
                cls._context.close()
            finally:
                cls._context = None
                cls._login_page = None
                cls._owner_thread_id = None

            if cls._playwright is not None:
                try:
                    cls._playwright.stop()
                finally:
                    cls._playwright = None

    @classmethod
    def discard_context_reference(cls) -> None:
        """Forget a context that cannot be controlled from the current thread."""
        with cls._lock:
            cls._context = None
            cls._login_page = None
            cls._owner_thread_id = None
            cls._playwright = None

    @classmethod
    def context_status(cls) -> bool:
        with cls._lock:
            return cls._is_context_alive()
