# web_scraping.py
import pathlib, re, textwrap
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://enatega.com/"
RAW = pathlib.Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)
CLEAN = pathlib.Path("data/clean"); CLEAN.mkdir(parents=True, exist_ok=True)
RAW_HTML = RAW / "home_rendered.html"
CLEAN_TXT = CLEAN / "home_rendered.txt"

# minimal selectors that usually indicate real content is present
CONTENT_SELECTORS = [
    "main", "[role=main]", "section", "article", "h1", "h2", ".container", ".wrapper"
]

def render_page(url: str, wait_ms: int = 1200) -> tuple[str, str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=45_000)

        # try to dismiss common banners if present (best-effort, non-fatal)
        for text in ["Accept", "I agree", "Got it", "Allow all", "Accept all", "Close", "OK"]:
            try:
                page.get_by_text(text, exact=False).first.click(timeout=1000)
            except Exception:
                pass

        # auto-scroll to trigger lazy content
        page.evaluate("""
            () => new Promise(resolve => {
              let y = 0; const step = 600;
              const timer = setInterval(() => {
                window.scrollBy(0, step); y += step;
                if (y >= document.body.scrollHeight) { clearInterval(timer); resolve(); }
              }, 200);
            })
        """)
        page.wait_for_timeout(wait_ms)

        # wait for any meaningful content selector (non-fatal if not found)
        found = False
        for sel in CONTENT_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=3000)
                found = True
                break
            except PWTimeout:
                continue

        # get rendered HTML (for debugging) and rendered visible text (more robust)
        html = page.content()
        try:
            rendered_text = page.locator("body").inner_text(timeout=2000)
        except Exception:
            rendered_text = ""

        browser.close()
        return html, rendered_text

def clean_main_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template", "svg", "canvas"]):
        tag.decompose()

    # remove header/nav/footer explicitly
    for sel in ["header", "nav", "footer", "[role=navigation]"]:
        for t in soup.select(sel):
            t.decompose()

    main = soup.select_one("main, [role=main], article, section") or soup.body or soup
    text = " ".join(s.strip() for s in main.stripped_strings if s)
    return re.sub(r"\s+", " ", text).strip()


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    # drop obvious junk placeholders that sometimes show up
    text = text.replace("[countdown_timer]", "").strip()
    return text

def preview(text: str, n=900) -> str:
    return textwrap.shorten(text, width=n, placeholder="…")

def main():
    html, rendered_text = render_page(URL)

    RAW_HTML.write_text(html, encoding="utf-8")

    # first try HTML-based extraction
    cleaned = normalize(clean_main_text_from_html(html))

    # fallback: if too short, prefer rendered visible text from the browser
    if len(cleaned.split()) < 60 and rendered_text:
        cleaned = normalize(rendered_text)

    CLEAN_TXT.write_text(cleaned, encoding="utf-8")

    # metadata
    title = ""
    try:
        soup = BeautifulSoup(html, "lxml")
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    except Exception:
        pass

    print(f"Rendered HTML → {RAW_HTML.resolve()}")
    print(f"Clean text    → {CLEAN_TXT.resolve()}")
    print(f"Title: {title}")
    # quick headings from HTML (may be empty on heavy-SPAs)
    try:
        main = BeautifulSoup(html, "lxml").select_one("main, [role=main], article, .content, .container, .wrapper")
        headings = [h.get_text(strip=True) for h in (main or BeautifulSoup(html, "lxml")).select("h1, h2, h3")]
    except Exception:
        headings = []
    print(f"Headings (first 10): {headings[:10]}")
    print(f"Characters: {len(cleaned)} | Words: {len(cleaned.split())}")
    print("\nPreview (~900 chars):\n", preview(cleaned, 900))

if __name__ == "__main__":
    main()
