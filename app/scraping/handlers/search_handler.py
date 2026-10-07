import time
from urllib.parse import urlparse, parse_qs

class SearchHandler:
    """
    Handles product search in Shopee based on the provided keyword.
    """
    def __init__(self, keyword):
        self.keyword = keyword

    def search(self, sb):
        print(f"[INFO] Searching for keyword: {self.keyword}")
        try:
            # Clear prior text and submit with Enter. Desktop mouse coordinates
            # can miss the button after a window resize or display scaling.
            sb.cdp.type("input.shopee-searchbar-input__input", self.keyword + '\n')
            print("[INFO] Submitted search keyword.")
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to enter search keyword: {e}")

        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                current = urlparse(sb.cdp.get_current_url())
                if current.path.rstrip('/') == '/search' and parse_qs(current.query).get('keyword') == [self.keyword]:
                    break
                if any(part in current.path for part in ('/verify', '/captcha', '/buyer/login')):
                    raise RuntimeError('Shopee redirected search to login or verification.')
                sb.sleep(0.5)
            else:
                raise RuntimeError('Search did not navigate after pressing Enter within 30 seconds.')
            sb.sleep(2)
            print("[INFO] Search results opened.")
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to click search button: {e}")

        total_pages = 1
        try:
            sb.cdp.wait_for_element_visible("span.shopee-mini-page-controller__total", timeout=10)
            total_pages = int(sb.cdp.get_text("span.shopee-mini-page-controller__total"))
            print(f"[INFO] Successfully retrieved total pages: {total_pages}")
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to retrieve total pages: {e}")

        return total_pages



