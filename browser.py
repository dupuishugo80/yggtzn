import glob
import json
import logging
import os
import re
import threading
from pathlib import Path
from seleniumbase import SB
from seleniumbase.core.download_helper import get_downloads_folder
from config import YGG_USERNAME, YGG_PASSWORD, YGG_BASE_URL, HEADLESS, MAX_SEARCH_PAGES

log = logging.getLogger(__name__)

COOKIES_PATH = Path(__file__).parent / "cookies.json"
PASSKEY_PATH = Path(__file__).parent / "passkey.txt"
DEBUG_DIR = Path(__file__).parent / "data"
LOGIN_RETRIES = 3


class YGGBrowser:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.sb = None
            cls._instance.logged_in = False
            cls._instance._sb_context = None
            cls._instance._lock = threading.Lock()
            cls._instance.passkey = None
        return cls._instance

    def _start_browser(self):
        if self.sb:
            return
        self._download_dir = get_downloads_folder()
        os.makedirs(self._download_dir, exist_ok=True)
        log.info("Starting SeleniumBase UC browser (downloads → %s)…", self._download_dir)
        self._sb_context = SB(
            uc=True,
            headed=not HEADLESS,
            headless2=HEADLESS,
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu",
        )
        self.sb = self._sb_context.__enter__()

    def _handle_cf(self):
        try:
            self.sb.uc_gui_handle_cf()
            self.sb.sleep(2)
        except BaseException:
            pass

    def _open_with_cf(self, url, reconnect_time=10):
        if url.rstrip("/") != YGG_BASE_URL.rstrip("/"):
            log.debug("Navigating to homepage first for CF clearance")
            self.sb.uc_open_with_reconnect(YGG_BASE_URL, reconnect_time=reconnect_time)
            self.sb.sleep(2)
            self._handle_cf()

        self.sb.uc_open_with_reconnect(url, reconnect_time=reconnect_time)
        self.sb.sleep(2)
        self._handle_cf()
        self._dismiss_popup()

    def _dismiss_popup(self):
        try:
            if self.sb.is_element_visible("#turboPromoClose"):
                self.sb.click("#turboPromoClose")
                log.debug("Dismissed turbo promo popup")
        except Exception:
            pass

    def _fetch_passkey(self):
        log.info("Fetching passkey from account page…")
        self._open_with_cf(f"{YGG_BASE_URL}/user/account", reconnect_time=6)
        try:
            el = self.sb.find_element("#profile_passkey")
            pk = el.text.strip()
            if pk:
                self.passkey = pk
                PASSKEY_PATH.write_text(pk, encoding="utf-8")
                log.info("Passkey saved (%s…)", pk[:6])
            else:
                log.warning("Passkey element found but empty")
        except Exception as e:
            log.error("Failed to extract passkey: %s", e)
            self._save_debug("passkey_fetch_fail")

    def _load_passkey(self) -> bool:
        if not PASSKEY_PATH.exists():
            return False
        try:
            pk = PASSKEY_PATH.read_text(encoding="utf-8").strip()
            if pk:
                self.passkey = pk
                log.info("Passkey loaded from file (%s…)", pk[:6])
                return True
        except OSError as e:
            log.warning("Failed to read passkey file: %s", e)
        return False

    def _save_cookies(self):
        cookies = self.sb.get_cookies()
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        log.info("Cookies saved to %s (%d cookies)", COOKIES_PATH, len(cookies))

    def _load_cookies(self) -> bool:
        if not COOKIES_PATH.exists():
            log.info("No cookies file found")
            return False

        try:
            cookies = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to read cookies: %s", e)
            return False

        self._open_with_cf(YGG_BASE_URL)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("httpOnly", None)
            try:
                self.sb.add_cookie(cookie)
            except Exception as e:
                log.debug("Skipping cookie %s: %s", cookie.get("name"), e)

        log.info("Loaded %d cookies from file", len(cookies))
        return True

    def _is_logged_in(self) -> bool:
        self._open_with_cf(YGG_BASE_URL)
        page = self.sb.get_page_source()
        return "Mon compte" in page

    def _save_debug(self, name):
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            self.sb.save_screenshot(str(DEBUG_DIR / f"{name}.png"))
            src = self.sb.get_page_source()[:1000]
            log.warning("Debug [%s] URL=%s page_source=%.500s", name, self.sb.get_current_url(), src)
        except Exception as e:
            log.warning("Could not save debug info: %s", e)

    def login(self):
        if self.logged_in:
            return

        self._start_browser()

        if self._load_cookies():
            if self._is_logged_in():
                self.logged_in = True
                log.info("Session restored from cookies")
                if not self._load_passkey():
                    self._fetch_passkey()
                return
            else:
                log.warning("Cookies loaded but session invalid (no 'Mon compte') — deleting cookies")
                COOKIES_PATH.unlink(missing_ok=True)
                self.sb.delete_all_cookies()

        log.info("Cookies expired or missing, performing full login…")
        login_url = f"{YGG_BASE_URL}/auth/login"

        for attempt in range(1, LOGIN_RETRIES + 1):
            log.info("Login attempt %d/%d — Opening %s", attempt, LOGIN_RETRIES, login_url)
            self._open_with_cf(login_url)

            if self.sb.is_element_visible('input[name="id"]'):
                break

            log.warning("Login form not found (attempt %d/%d)", attempt, LOGIN_RETRIES)
            self._save_debug(f"login_attempt_{attempt}")

            if attempt < LOGIN_RETRIES:
                self.sb.sleep(5)

        if not self.sb.is_element_visible('input[name="id"]'):
            log.error("Login form not found after %d attempts, giving up", LOGIN_RETRIES)
            self._save_debug("login_final_fail")
            return

        log.info("Filling login form…")
        self.sb.type('input[name="id"]', YGG_USERNAME)
        self.sb.type('input[name="pass"]', YGG_PASSWORD)
        self.sb.click('button[type="submit"]')

        self.sb.sleep(3)
        self._dismiss_popup()

        if self._is_logged_in():
            self.logged_in = True
            self._save_cookies()
            self._fetch_passkey()
            log.info("Login successful, cookies and passkey saved")
        else:
            log.error("Login failed — 'Mon compte' not found on page")

    def search(self, query: str, category: int = None, sub_category: int = None) -> list[dict]:
        with self._lock:
            if not self.logged_in:
                self.login()

            search_query = query.replace(" ", "+")
            base_url = f"{YGG_BASE_URL}/engine/search?name={search_query}&do=search"
            if category:
                base_url += f"&category={category}"
            if sub_category:
                base_url += f"&sub_category={sub_category}"

            all_results = []
            for page_num in range(MAX_SEARCH_PAGES):
                page_url = base_url if page_num == 0 else f"{base_url}&page={page_num * 50}"
                log.info("Searching page %d: %s", page_num + 1, page_url)
                self._open_with_cf(page_url, reconnect_time=6)

                if page_num == 0:
                    session_ok = self._check_session()
                    if not self.logged_in:
                        log.error("Could not restore session, aborting search")
                        return []
                    if not session_ok:
                        log.info("Re-navigating to search page after re-login")
                        self._open_with_cf(page_url, reconnect_time=6)

                page_results = self._parse_results()
                all_results.extend(page_results)

                if len(page_results) < 50:
                    break

            log.info("Found %d total results across %d page(s)", len(all_results), page_num + 1)
            return all_results

    def _check_session(self) -> bool:
        """Return True if session was valid, False if re-login was needed."""
        page = self.sb.get_page_source()
        if "Mon compte" not in page:
            log.warning("Session expired — re-logging in")
            self._save_debug("session_expired")
            self.logged_in = False
            self.login()
            return False
        return True

    def _parse_results(self) -> list[dict]:
        results = []
        rows = self.sb.find_elements("table.table tbody tr")
        if not rows:
            log.warning("No table rows found on search page — URL: %s", self.sb.get_current_url())
            self._save_debug("no_results")
        for row in rows:
            try:
                cols = row.find_elements("css selector", "td")
                if len(cols) < 9:
                    continue

                cat_div = cols[0].find_element("css selector", "div.hidden")
                subcat = cat_div.get_attribute("textContent").strip()

                name_el = cols[1].find_element("css selector", "a#torrent_name")
                title = name_el.text.strip()
                link = name_el.get_attribute("href")

                match = re.search(r"/(\d+)-", link)
                torrent_id = match.group(1) if match else ""

                size = self._parse_size(cols[5].text.strip())
                seeders = int(cols[7].text.strip())
                leechers = int(cols[8].text.strip())

                results.append({
                    "title": title,
                    "link": link,
                    "torrent_id": torrent_id,
                    "size": size,
                    "seeders": seeders,
                    "leechers": leechers,
                    "subcat": subcat,
                })
            except Exception as e:
                log.debug("Skipping row: %s", e)
                continue
        return results

    def download(self, torrent_page_url: str) -> bytes | None:
        with self._lock:
            if not self.logged_in:
                self.login()

            log.info("Opening torrent page: %s", torrent_page_url)
            self._open_with_cf(torrent_page_url, reconnect_time=6)

            for f in glob.glob(os.path.join(self._download_dir, "*.torrent")):
                os.remove(f)

            self.sb.click('#download-timer-btn')
            log.info("Waiting for download timer…")

            self.sb.wait_for_element('#downloadTimerLink.ready', timeout=35)
            self.sb.wait_for_element_not_visible('#downloadTimerLink[style*="display: none"]', timeout=5)
            self.sb.sleep(1)

            self.sb.click('#downloadTimerLink')
            log.info("Clicked download link, waiting for file…")

            torrent_file = None
            for _ in range(15):
                self.sb.sleep(1)
                files = glob.glob(os.path.join(self._download_dir, "*.torrent"))
                if files:
                    torrent_file = files[0]
                    break

            if not torrent_file:
                log.error("No .torrent file found in %s", self._download_dir)
                return None, None

            filename = os.path.basename(torrent_file)
            data = Path(torrent_file).read_bytes()
            os.remove(torrent_file)
            log.info("Downloaded %s (%d bytes)", filename, len(data))
            return data, filename

    @staticmethod
    def _parse_size(text: str) -> int:
        text = text.upper().replace(",", ".").strip()
        multipliers = {"KO": 1024, "KB": 1024, "MO": 1024**2, "MB": 1024**2,
                       "GO": 1024**3, "GB": 1024**3, "TO": 1024**4, "TB": 1024**4}
        for suffix, mult in multipliers.items():
            if suffix in text:
                try:
                    return int(float(text.replace(suffix, "").strip()) * mult)
                except ValueError:
                    return 0
        try:
            return int(text)
        except ValueError:
            return 0

    def close(self):
        if self._sb_context:
            try:
                self._sb_context.__exit__(None, None, None)
            except Exception:
                pass
            self.sb = None
            self._sb_context = None
            self.logged_in = False


browser = YGGBrowser()
