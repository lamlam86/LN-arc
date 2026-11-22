#!/usr/bin/env python3
"""Google dork runner for authorized reconnaissance (Playwright).

Drives Google Search through a real browser so the engine supplies its own
session parameters, then returns the organic result title + URL pairs. It is a
discovery step only: it never opens a result, logs in, or bypasses a challenge
automatically. Use --csv/--json to feed doc_pii_scan.py, which does the
read-only document triage.

This script is part of the LN-ARC google-dork-pii skill. Only run it against
assets you are authorized to assess, and keep the request rate low.
"""

import argparse
import html
import os
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

CONSENT_TEXTS = (
    "Before you continue",
    "Trước khi bạn tiếp tục",
    "We use cookies",
    "Chúng tôi sử dụng cookie",
)
BLOCK_TEXTS = (
    "Our systems have detected unusual traffic",
    "unusual traffic from your computer",
    "hệ thống của chúng tôi đã phát hiện lưu lượng truy cập bất thường",
)

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""

SYSTEM_CHROME = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
)


def find_system_chrome() -> str | None:
    for path in SYSTEM_CHROME:
        if Path(path).exists():
            return path
    return None

def human_pause(lo: float = 2.0, hi: float = 5.0) -> None:
    time.sleep(random.uniform(lo, hi))

def accept_consent(page) -> None:
    body = page.text_content("body")[:2000]
    if not any(t.lower() in body.lower() for t in CONSENT_TEXTS):
        return
    for sel in (
        "button#L2AGLb",
        "button:has-text('Accept all')",
        "button:has-text('Tôi đồng ý')",
        "button:has-text('Accept')",
    ):
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                human_pause(1, 2)
                return
        except (PWTimeout, PWError):
            continue


def is_blocked(page) -> bool:
    if "/sorry/" in page.url:
        return True
    if page.locator("form#captcha-form, div.g-recaptcha, iframe[src*='recaptcha']").count():
        return True
    try:
        body = page.text_content("body")[:3000].lower()
    except PWError:
        return False
    return any(t.lower() in body for t in BLOCK_TEXTS)


def click_captcha(page) -> bool:
    """Bấm checkbox reCAPTCHA ("Tôi không phải là robot") nếu có."""
    selectors = (
        "iframe[src*='recaptcha/api2/anchor']",
        "iframe[title*='reCAPTCHA']",
        "iframe[title*='recaptcha']",
        "iframe[src*='recaptcha']",
    )
    for sel in selectors:
        try:
            frame = page.frame_locator(sel)
            box = frame.locator("#recaptcha-anchor, .recaptcha-checkbox-border")
            if box.count():
                box.first.click(timeout=3000)
                page.wait_for_timeout(2500)
                return True
        except (PWError, PWTimeout):
            continue
    return False


def has_no_results(page) -> bool:
    try:
        body = (page.text_content("#search, #botstuff") or "")[:3000].lower()
    except PWError:
        return False
    return "did not match any documents" in body or "không khớp với bất kỳ tài liệu nào" in body


def looks_like_interstitial(page) -> bool:
    """Trang đệm "cần bật JS"/trang trắng: chưa có SERP và cũng chưa có CAPTCHA."""
    if page.locator("form#captcha-form, div.g-recaptcha, iframe[src*='recaptcha']").count():
        return False
    if page.locator("div#search, div#rso, div#botstuff").count():
        return False
    try:
        return len((page.text_content("body") or "")[:500].strip()) < 200
    except PWError:
        return False
 

def reload_if_interstitial(page, attempts: int = 2) -> None:
    """F5 vài lần nếu chỉ gặp trang đệm (không phải CAPTCHA)."""
    for i in range(attempts):
        if not looks_like_interstitial(page):
            return
        print(f"[*] Trang đệm/trắng, F5 lần {i + 1}...")
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
        except PWError:
            return


RESOLVE_DELAY = (1.0, 2.5)

META_RE = re.compile(r'<meta[^>]+content="\s*(\d+)\s*;\s*url=([^"]+)"', re.I)
SITE_RE = re.compile(r"site:(\S+)", re.I)


def normalize_dork(dork: str) -> str:
    """Sửa toán tử bị gõ/nhập thành '=' (vd filetype=pdf -> filetype:pdf)."""
    ops = ("site", "filetype", "inurl", "intitle", "intext",
           "allinurl", "allintitle", "ext", "before", "after")
    pat = re.compile(r"\b(" + "|".join(ops) + r")\s*=\s*", re.I)
    return pat.sub(lambda m: m.group(1).lower() + ":", dork)


def split_or_terms(inner: str) -> list[str]:
    """Tách 'a OR b OR c' theo OR, tôn trọng dấu ngoặc kép."""
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif inner[i:i + 4].upper() == " OR ":
            out.append("".join(buf).strip())
            buf = []
            i += 4
            continue
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf).strip())
    return [x for x in out if x]


def expand_or_dorks(dork: str) -> list[str]:
    """'site:x (A OR B) pdf' -> ['site:x A pdf', 'site:x B pdf']."""
    m = re.search(r"\(([^()]*\bOR\b[^()]*)\)", dork, re.I)
    if not m:
        return [dork]
    alts = split_or_terms(m.group(1))
    if len(alts) < 2:
        return [dork]
    prefix, suffix = dork[:m.start()], dork[m.end():]
    return [re.sub(r"\s+", " ", f"{prefix} {a} {suffix}").strip() for a in alts]


def site_hosts_from(dork: str) -> list[str]:
    """Lấy host trong các toán tử site: để lọc kết quả ngoài domain."""
    hosts: list[str] = []
    for raw in SITE_RE.findall(dork or ""):
        host = raw.strip("\"'()[]").lower().split("/")[0]
        if host.startswith("*."):
            host = host[2:]
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def unwrap_url(href: str) -> str:
    """Tách URL đích khỏi /url?q=... cục bộ, KHÔNG gửi request."""
    for prefix in ("/url?q=", "https://www.google.com/url?q="):
        if href.startswith(prefix):
            return urllib.parse.unquote(href[len(prefix):].split("&")[0])
    return href


def resolve_href(request_ctx, href: str, attempts: int = 4) -> str:
    """Google trả /goto?url=<token>; đôi khi chèn trang meta-refresh "chờ N giây"
    (throttle). Gặp trang đó thì đợi đúng N giây rồi thử lại cùng link.
    """
    if not href:
        return href
    if href.startswith("/url?q="):
        return urllib.parse.unquote(href[len("/url?q="):].split("&")[0])

    full = href if href.startswith("http") else "https://www.google.com" + href
    for _ in range(attempts):
        time.sleep(random.uniform(*RESOLVE_DELAY))
        try:
            r = request_ctx.get(full, max_redirects=0, timeout=20000)
        except PWError:
            return ""
        loc = r.headers.get("location")
        if loc:
            return loc
        if r.status == 200:
            m = META_RE.search(r.text())
            if not m:
                return ""
            wait = min(int(m.group(1)), 8)
            nxt = html.unescape(m.group(2))
            full = nxt if nxt.startswith("http") else "https://www.google.com" + nxt
            time.sleep(wait + random.uniform(0.2, 0.9))
            continue
        return ""
    return ""


def click_next(page) -> bool:
    """Bấm nút Next như người dùng thật (giữ đúng tham số phiên của Google)."""
    nxt = page.locator("a#pnnext")
    try:
        if nxt.count() and nxt.first.is_visible():
            nxt.first.click(timeout=5000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            page.wait_for_timeout(1800)
            return True
    except PWError:
        pass
    return False


def wait_results(page, timeout_ms: int = 20000) -> bool:
    """Chờ tới khi khối kết quả organic (#rso) thực sự render xong."""
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('div#rso a h3').length > 0",
            timeout=timeout_ms,
        )
        return True
    except PWTimeout:
        return False


def extract_results(page, limit: int, request_ctx=None,
                    allowed_hosts: list[str] | None = None,
                    stats: dict | None = None) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    st = stats if stats is not None else {}
    for k in ("anchors", "no_h3", "no_href", "non_http", "google", "bad_host", "dup"):
        st.setdefault(k, 0)
    st.setdefault("bad_samples", [])

    anchors = page.locator(
        "div#rso a[jsname='UWckNb'], div#rso a:has(h3)"
    ).all()
    st["anchors"] += len(anchors)
    for a in anchors:
        try:
            h3 = a.locator("h3")
            if not h3.count():
                st["no_h3"] += 1
                continue
            title = (h3.first.text_content() or "").strip()
            href = a.get_attribute("href") or ""
            if not href:
                st["no_href"] += 1
                continue
            href = resolve_href(request_ctx, href) if request_ctx else unwrap_url(href)
            if not re.match(r"^https?://", href):
                st["non_http"] += 1
                continue
            if re.match(r"^https?://([a-z0-9-]+\.)*google\.[a-z.]+/", href):
                st["google"] += 1
                continue
            host = (urllib.parse.urlparse(href).hostname or "").lower().rstrip(".")
            if not host:
                st["bad_host"] += 1
                continue
            if allowed_hosts and not any(
                host == h or host.endswith("." + h) for h in allowed_hosts
            ):
                st["bad_host"] += 1
                if len(st["bad_samples"]) < 5:
                    st["bad_samples"].append(href[:160])
                continue
            if href in seen:
                st["dup"] += 1
                continue
            seen.add(href)
            results.append((re.sub(r"\s+", " ", title) or href, href))
            if len(results) >= limit:
                break
        except PWError:
            continue
    return results


def search_via_ui(page, dork: str) -> None:
    """Gõ dork vào ô tìm kiếm để Google tự sinh sxsrf/ei như người dùng thật."""
    page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=30000)
    accept_consent(page)
    box = page.locator("textarea[name=q], input[name=q]").first
    box.wait_for(state="visible", timeout=15000)
    box.click()
    box.fill(dork)
    human_pause(0.4, 1.2)
    box.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=30000)


def next_page_url(base_url: str, dork: str, start: int, basic_html: bool = False) -> str:
    """Giữ nguyên tham số của lần search trước (sxsrf, ei, sca_esv...) rồi đổi start."""
    parsed = urllib.parse.urlparse(base_url)
    if parsed.path.endswith("/search") and "/sorry/" not in parsed.path:
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        qs["start"] = [str(start)]
        if basic_html:
            qs["gbv"] = ["1"]
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(qs, doseq=True)))
    params = {"q": dork, "start": start, "hl": "en", "gl": "us"}
    if basic_html:
        params["gbv"] = "1"
    return "https://www.google.com/search?" + urllib.parse.urlencode(params)


def wait_for_captcha(page, seconds: int) -> bool:
    """Chờ người dùng giải CAPTCHA trong cửa sổ; trả True nếu đã qua."""
    deadline = time.time() + seconds
    print(f"[!] Đang chờ bạn giải CAPTCHA trong cửa sổ (tối đa {seconds}s)...")
    if click_captcha(page):
        print("[*] Đã bấm checkbox reCAPTCHA.")
    while time.time() < deadline:
        time.sleep(4)
        try:
            if not is_blocked(page):
                print("[+] Đã qua chặn.")
                return True
        except PWError:
            return False
    return False


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Google dork bằng Playwright")
    ap.add_argument("--query", help="dork thô (ưu tiên cao nhất)")
    ap.add_argument("--url", help="URL Google Search đầy đủ")
    ap.add_argument("--domain", default="", help="site: domain when --query/--url are omitted")
    ap.add_argument("--ext", default="pdf", help="filetype, bỏ trống để không lọc")
    ap.add_argument("--term", default="CCCD", help="từ khoá trong ngoặc kép")
    ap.add_argument("--num", type=int, default=10, help="tổng số kết quả muốn lấy")
    ap.add_argument("--start", type=int, default=0, help="vị trí bắt đầu (bội số của 10)")
    ap.add_argument("--pages", type=int, default=2, help="số trang tối đa")
    ap.add_argument("--headful", action="store_true", help="hiện cửa sổ trình duyệt")
    ap.add_argument("--xvfb", action="store_true",
                    help="chạy headful trong Xvfb (giống Chrome thật, không hiện cửa sổ)")
    ap.add_argument("--profile", default="chrome-profile",
                    help="thư mục persistent context (giữ cookie/phiên đăng nhập)")
    ap.add_argument("--chrome-path", help="đường dẫn Chromium/Chrome")
    ap.add_argument("--proxy", help="proxy dạng http://host:port")
    ap.add_argument("--user-agent", help="UA tuỳ chỉnh (ví dụ UA Chrome trên Windows)")
    ap.add_argument("--delay-min", type=float, default=1.0, help="giãn cách tối thiểu khi mở link /goto (giây)")
    ap.add_argument("--delay-max", type=float, default=2.5, help="giãn cách tối đa khi mở link /goto (giây)")
    ap.add_argument("--block-retries", type=int, default=2,
                    help="số lần F5 khi bị chặn (headless vẫn dùng được)")
    ap.add_argument("--wait-captcha", type=int, default=0,
                    help="giây chờ bạn tự giải CAPTCHA (cần --headful)")
    ap.add_argument("--dump", default="google_blocked.html", help="file lưu HTML khi bị chặn")
    ap.add_argument("--no-site-filter", action="store_true",
                    help="không lọc theo site: trong dork (mặc định có lọc)")
    ap.add_argument("--basic-html", action="store_true",
                    help="dùng bản HTML cơ bản (gbv=1): ít bị chặn, tôn trọng site: ở các trang sau")
    ap.add_argument("--split-or", dest="split_or", action="store_true", default=True,
                    help="tách (A OR B ...) thành nhiều query riêng, mỗi query giữ nguyên site: (mặc định bật)")
    ap.add_argument("--no-split-or", dest="split_or", action="store_false",
                    help="giữ nguyên dork có (A OR B) như một query duy nhất")
    ap.add_argument("--print-url-only", action="store_true",
                    help="chỉ in URL Google Search của dork, không mở trình duyệt")
    ap.add_argument("--csv", help="ghi kết quả ra file CSV")
    ap.add_argument("--json", help="write results to a JSON file (title/url pairs)")
    args = ap.parse_args()

    global RESOLVE_DELAY
    RESOLVE_DELAY = (args.delay_min, args.delay_max)

    if args.query:
        dork = args.query
    elif args.url:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(args.url).query)
        dork = (qs.get("q") or [""])[0]
        if not dork:
            sys.exit("URL không có tham số q.")
    elif args.domain:
        parts = [f"site:{args.domain}"]
        if args.ext:
            parts.append(f"filetype:{args.ext}")
        if args.term:
            parts.append(f'"{args.term}"')
        dork = " ".join(parts)
    else:
        sys.exit("Provide --query (preferred), --url, or --domain.")

    dork = normalize_dork(dork)

    if "..." in dork or "…" in dork:
        sys.exit("[!] Dork đang chứa '...' (placeholder). Hãy dán query đầy đủ, "
                 "đừng để 'filetype:pdf OR ...'.")

    dorks = expand_or_dorks(dork) if args.split_or else [dork]

    if args.print_url_only:
        if args.url and len(dorks) == 1 and not args.basic_html:
            print(args.url)
        else:
            for d in dorks:
                print(next_page_url("", d, args.start, args.basic_html))
        return

    if args.xvfb and os.environ.get("GDORK_XVFB") != "1":
        argv = [a for a in sys.argv[1:] if a != "--xvfb"]
        if "--headful" not in argv:
            argv.append("--headful")
        env = dict(os.environ, GDORK_XVFB="1")
        print("[*] Chạy lại trong Xvfb (headful ẩn)...", flush=True)
        os.execvpe(
            "xvfb-run",
            ["xvfb-run", "-a", "-s", "-screen 0 1366x900x24",
             sys.executable, sys.argv[0], *argv],
            env,
        )
        return

    print(f"[*] Dork   : {dork}")
    print(f"[*] Profile: {args.profile}")

    allowed_hosts = [] if args.no_site_filter else site_hosts_from(dork)
    if allowed_hosts:
        print(f"[i] Chỉ giữ kết quả thuộc: {', '.join(allowed_hosts)}")

    profile_dir = Path(args.profile).absolute()
    profile_dir.mkdir(parents=True, exist_ok=True)

    launch_kwargs = dict(
        user_data_dir=str(profile_dir),
        headless=not args.headful,
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
        viewport={"width": 1366, "height": 900},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
        ],
    )
    if args.chrome_path:
        launch_kwargs["executable_path"] = args.chrome_path
    if args.proxy:
        launch_kwargs["proxy"] = {"server": args.proxy}
    if args.user_agent:
        launch_kwargs["user_agent"] = args.user_agent

    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    base_url = ""

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(**launch_kwargs)
        except PWError as exc:
            msg = str(exc)
            fallback = find_system_chrome() if not args.chrome_path else None
            if "Executable doesn't exist" in msg and fallback:
                print(f"[*] Chromium của Playwright chưa cài, dùng {fallback}")
                launch_kwargs["executable_path"] = fallback
                try:
                    ctx = pw.chromium.launch_persistent_context(**launch_kwargs)
                except PWError as exc2:
                    sys.exit(f"Không mở được Chromium: {exc2}")
            elif "Executable doesn't exist" in msg:
                sys.exit("Thiếu trình duyệt: python3 -m playwright install chromium "
                         "hoặc dùng --chrome-path /usr/bin/chromium")
            else:
                sys.exit(f"Không mở được Chromium: {exc}")

        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            first = True
            for step in range(len(dorks) * args.pages):
                d_i, page_idx = divmod(step, args.pages)
                dork_q = dorks[d_i]
                if page_idx == 0:
                    first = True
                    base_url = ""
                    if d_i > 0:
                        print(f"\n[*] Query {d_i + 1}/{len(dorks)}: {dork_q}")
                        human_pause(8, 15)
                if len(results) >= args.num:
                    break
                start = args.start + page_idx * 10

                if first and args.url and len(dorks) == 1 and not args.basic_html:
                    print(f"[*] Mở URL của bạn: {args.url[:160]}...")
                    page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
                elif first and args.basic_html:
                    url = next_page_url("", dork_q, start, True)
                    print(f"[*] Mở bản HTML cơ bản: {url[:120]}...")
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                elif first:
                    print("[*] Tìm qua ô search.")
                    search_via_ui(page, dork_q)
                else:
                    human_pause(6, 12)
                    if not click_next(page):
                        url = next_page_url(base_url, dork_q, start, args.basic_html)
                        print(f"[*] Không thấy nút Next, mở theo start={start}")
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)

                first = False
                accept_consent(page)
                try:
                    page.wait_for_selector(
                        "div#search, div#botstuff, div#main, form#captcha-form",
                        timeout=15000,
                    )
                except PWTimeout:
                    pass
                reload_if_interstitial(page)

                if "/sorry/" not in page.url and "/search" in page.url:
                    base_url = page.url
                    print(f"[i] URL thực tế: {base_url}")

                if is_blocked(page):
                    recovered = False
                    if args.headful and args.wait_captcha and wait_for_captcha(page, args.wait_captcha):
                        recovered = True
                    # Headless: chỉ F5 lại trang (không tự bấm/giải CAPTCHA)
                    for k in range(args.block_retries if not recovered else 0):
                        print(f"[*] Bị chặn, F5 lần {k + 1}/{args.block_retries}...")
                        time.sleep(random.uniform(8, 15))
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=30000)
                            page.wait_for_timeout(2500)
                        except PWError:
                            break
                        reload_if_interstitial(page)
                        if is_blocked(page):
                            if click_captcha(page):
                                print("[*] Đã bấm checkbox reCAPTCHA, chờ kết quả...")
                        if not is_blocked(page):
                            recovered = True
                            break

                    if recovered:
                        accept_consent(page)
                        reload_if_interstitial(page)
                        if page.locator("div#search, div#botstuff").count() == 0:
                            url = args.url if (page_idx == 0 and args.url and len(dorks) == 1 and not args.basic_html) else next_page_url(base_url, dork_q, start, args.basic_html)
                            print(f"[*] Mở lại query: {url[:150]}")
                            page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            accept_consent(page)
                            try:
                                page.wait_for_selector("div#search, div#botstuff", timeout=15000)
                            except PWTimeout:
                                pass
                    else:
                        try:
                            Path(args.dump).write_text(page.content(), encoding="utf-8")
                            print(f"[!] Google chặn bot. HTML: {args.dump}")
                        except PWError:
                            print("[!] Google chặn bot (không lưu được HTML: trang đã đóng).")
                        print("[!] Cần IP khác (--proxy), hoặc --headful --wait-captcha 180 "
                              "để tự giải CAPTCHA, hoặc đăng nhập Google trong profile.")
                        print(f"[i] Giữ {len(results)} kết quả đã lấy được trước khi bị chặn.")
                        break

                if has_no_results(page):
                    print("[-] Hết kết quả (Google báo không khớp tài liệu nào).")
                    break

                if not wait_results(page):
                    print(f"[!] Trang {page_idx + 1}: chưa thấy kết quả render, thử reload...")
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=30000)
                        accept_consent(page)
                    except PWError:
                        pass
                    if not wait_results(page, 10000):
                        if args.dump and args.dump != "/dev/null":
                            dump = Path(args.dump).with_name(
                                f"{Path(args.dump).stem}_p{page_idx + 1}.html"
                            )
                            try:
                                dump.write_text(page.content(), encoding="utf-8")
                                print(f"[!] Không thấy kết quả ở trang {page_idx + 1}. HTML: {dump}")
                            except PWError:
                                print(f"[!] Không thấy kết quả ở trang {page_idx + 1}.")
                        else:
                            print(f"[!] Không thấy kết quả ở trang {page_idx + 1}.")
                        if page_idx + 1 < args.pages:
                            continue
                        break

                stats: dict = {}
                new: list[tuple[str, str]] = []
                for title, link in extract_results(
                    page, args.num - len(results), ctx.request, allowed_hosts, stats
                ):
                    if link in seen_urls:
                        stats["dup"] = stats.get("dup", 0) + 1
                        continue
                    seen_urls.add(link)
                    new.append((title, link))

                if (not new and stats.get("anchors")
                        and stats.get("bad_host") == stats.get("anchors")
                        and not args.basic_html):
                    print("[*] Google bỏ 'site:' — thử lại bằng bản HTML cơ bản (gbv=1)...")
                    try:
                        page.goto(next_page_url(base_url, dork_q, start, True),
                                  wait_until="domcontentloaded", timeout=30000)
                        accept_consent(page)
                        wait_results(page, 15000)
                        stats = {}
                        new = []
                        for title, link in extract_results(
                            page, args.num - len(results), ctx.request, allowed_hosts, stats
                        ):
                            if link in seen_urls:
                                stats["dup"] = stats.get("dup", 0) + 1
                                continue
                            seen_urls.add(link)
                            new.append((title, link))
                    except PWError:
                        pass

                if not new:
                    print(f"[-] Trang {page_idx + 1}: không có link mới "
                          f"(anchor={stats.get('anchors', 0)}, trùng={stats.get('dup', 0)}, "
                          f"sai host={stats.get('bad_host', 0)}, google={stats.get('google', 0)}).")
                    for sample in stats.get("bad_samples", []):
                        print(f"    bị loại: {sample}")
                    if stats.get("bad_host") == stats.get("anchors") and stats.get("anchors"):
                        print("    [!] Google đã bỏ 'site:' ở trang này (thường do OR lồng trong ngoặc).")
                        print("    [!] Dùng site: riêng cho từng nhánh, ví dụ:")
                        print('        site:camau.baohiemxahoi.gov.vn CCCD filetype:pdf OR '
                              'site:camau.baohiemxahoi.gov.vn "số điện thoại" filetype:pdf OR '
                              'site:camau.baohiemxahoi.gov.vn SĐT filetype:pdf')
                    if args.dump and args.dump != "/dev/null":
                        dump = Path(args.dump).with_name(
                            f"{Path(args.dump).stem}_p{page_idx + 1}.html"
                        )
                        try:
                            dump.write_text(page.content(), encoding="utf-8")
                            print(f"    HTML trang {page_idx + 1}: {dump}")
                        except PWError:
                            pass
                    if page_idx + 1 < args.pages:
                        print("[*] Thử sang trang kế tiếp...")
                        continue
                    break
                results.extend(new)
                for title, link in new:
                    print(f"  + {title}\n    {link}", flush=True)
        except PWError as exc:
            print("[!] Cửa sổ/trình duyệt đã bị đóng hoặc lỗi Playwright:",
                  str(exc).splitlines()[0])
        finally:
            try:
                ctx.close()
            except PWError:
                pass

    print(f"\n[+] Tổng {len(results)} kết quả\n")
    for i, (title, link) in enumerate(results, 1):
        print(f"{i:>2}. {title}")
        print(f"    {link}")

    if args.csv:
        import csv
        csv_path = Path(args.csv)
        old: list[tuple[str, str]] = []
        if csv_path.exists():
            try:
                with csv_path.open(newline="", encoding="utf-8") as fh:
                    old = [(r.get("title", ""), r.get("url", ""))
                           for r in csv.DictReader(fh) if r.get("url")]
            except (OSError, csv.Error):
                old = []
        merged: list[tuple[str, str]] = []
        merged_seen: set[str] = set()
        for title, link in old + results:
            if link in merged_seen:
                continue
            merged_seen.add(link)
            merged.append((title, link))
        if results or merged:
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["title", "url"])
                w.writerows(merged)
            print(f"\n[i] CSV: {len(merged)} dòng (thêm {len(merged) - len(old)}) -> {args.csv}")

    if args.json:
        import json
        json_path = Path(args.json)
        old: list[dict] = []
        if json_path.exists():
            try:
                raw = json.loads(json_path.read_text(encoding="utf-8"))
                rows = raw.get("results", []) if isinstance(raw, dict) else raw
                if isinstance(rows, list):
                    old = [r for r in rows if isinstance(r, dict) and r.get("url")]
            except (OSError, json.JSONDecodeError):
                old = []
        merged: list[dict] = []
        merged_seen: set[str] = set()
        for row in old + [{"title": t, "url": u} for t, u in results]:
            u = row.get("url")
            if not u or u in merged_seen:
                continue
            merged_seen.add(u)
            merged.append({"title": row.get("title", ""), "url": u})
        if merged:
            json_path.write_text(
                json.dumps({"query": dork, "results": merged}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[i] JSON: {len(merged)} dòng -> {args.json}")


if __name__ == "__main__":
    main()
