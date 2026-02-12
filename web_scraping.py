# web_scraping.py
import pathlib, re, textwrap
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URLS = [
#     "https://enatega.com/",

#     # Case studies
#     "https://enatega.com/yalla-delivery/",
#     "https://enatega.com/stylizenow/",
#     "https://enatega.com/easy-eats/",
#     "https://enatega.com/vinifynd/",
#     "https://enatega.com/snap-delivered/",
#     "https://enatega.com/borku-delivery/",

#     # Features
#     "https://enatega.com/multi-vendor-features/",
#     "https://enatega.com/multi-vendor-doc/overview-of-the-api/",
#     "https://enatega.com/multi-vendor-doc/prerequisites/",
   

#    # Competitors
#     "https://enatega.com/enatega-vs-blink/",
#     "https://enatega.com/enatega-vs-deonde/",
#     "https://enatega.com/enatega-vs-gloriafood/",
#     "https://enatega.com/enatega-vs-ordering-co/",
#     "https://enatega.com/enatega-vs-shipday/",
#     "https://enatega.com/enatega-vs-spotneats/",
#     "https://enatega.com/enatega-vs-yelo/",
#     "https://enatega.com/enatega-vs-zeew/",

    # Use cases
    # "https://enatega.com/gift-delivery-solution/",
    # "https://enatega.com/liquor-delivery-solution/",
    # "https://enatega.com/food-and-beverage-solution/",
    # "https://enatega.com/laundry-on-demand-services-solution/",
    # "https://enatega.com/milk-delivery-solution/",
    # "https://enatega.com/flower-delivery-solution/",
    # "https://enatega.com/courier-delivery-solution/",
    # "https://enatega.com/roadside-assistance-services-solution/",
    # "https://enatega.com/grocery-delivery-solution/",
    # "https://enatega.com/medicine-delivery-solution/",
    # "https://enatega.com/beauty-services-scheduling-solution/",
    # "https://enatega.com/document-delivery-solution/",

    # "https://enatega.com/multi-vendor-doc/introduction/",
    # "https://enatega.com/multi-vendor-doc/high-level-architecture/",
    # "https://enatega.com/multi-vendor-doc/overview-of-the-api/",
    # "https://enatega.com/multi-vendor-doc/faqs/",
    # "https://enatega.com/multi-vendor-doc/license/",
    # "https://enatega.com/multi-vendor-doc/patch-notes/",
    # "https://enatega.com/multi-vendor-doc/prerequisites/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-backend-api-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-web-dashboard-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-admin-dashboard-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-customer-app-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-rider-app-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-setup-restaurant-app-locally/",
    # "https://enatega.com/multi-vendor-doc/how-to-deploy-backend-api-server/",
    # "https://enatega.com/multi-vendor-doc/how-to-deploy-admin-dashboard/",
    # "https://enatega.com/multi-vendor-doc/how-to-deploy-web-dashboard/",
    # "https://enatega.com/multi-vendor-doc/how-to-deploy-mobile-applications/",
    # "https://enatega.com/multi-vendor-doc/configuration-google-maps-api-keys/",
    # "https://enatega.com/multi-vendor-doc/amplitude-introduction/",

    "https://enatega.com/lumi-super-ai-app/",
]

RAW = pathlib.Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)
CLEAN = pathlib.Path("data/clean"); CLEAN.mkdir(parents=True, exist_ok=True)

# selectors to detect visible content
CONTENT_SELECTORS = [
    "main", "[role=main]", "section", "article", "h1", "h2", ".container", ".wrapper"
]

def render_page(url: str, wait_ms: int = 1200) -> tuple[str, str]:
    """Render a page with Playwright, return (html, visible_text)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=45_000)

        # dismiss common banners
        for text in ["Accept", "I agree", "Got it", "Allow all", "Accept all", "Close", "OK"]:
            try:
                page.get_by_text(text, exact=False).first.click(timeout=1000)
            except Exception:
                pass

        # auto-scroll to load lazy content
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

        # wait for some content
        for sel in CONTENT_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=3000)
                break
            except PWTimeout:
                continue

        # dump both: full DOM (debugging) + visible text (preferred)
        html = page.content()
        try:
            visible_text = page.locator("body").inner_text(timeout=2000)
        except Exception:
            visible_text = ""

        browser.close()
        return html, visible_text

def normalize(text: str) -> str:
    """Basic cleanup for whitespace and junk placeholders."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.replace("[countdown_timer]", "").strip()

def preview(text: str, n=900) -> str:
    return textwrap.shorten(text, width=n, placeholder="…")

def main():
    for url in URLS:
        slug = url.rstrip("/").split("/")[-1] or "home"
        raw_file = RAW / f"{slug}.html"
        clean_file = CLEAN / f"{slug}.txt"

        html, visible_text = render_page(url)
        raw_file.write_text(html, encoding="utf-8")

        # ✅ Prefer visible text (user-facing only)
        cleaned = normalize(visible_text)
        if len(cleaned.split()) < 60:  # fallback if visible text too short
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript", "template", "svg", "canvas"]):
                tag.decompose()
            for sel in ["header", "nav", "footer", "[role=navigation]"]:
                for t in soup.select(sel):
                    t.decompose()
            main_tag = soup.select_one("main, [role=main], article, section") or soup.body or soup
            cleaned = normalize(" ".join(s.strip() for s in main_tag.stripped_strings if s))

        clean_file.write_text(cleaned, encoding="utf-8")

        # metadata
        title = ""
        try:
            soup = BeautifulSoup(html, "lxml")
            title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
        except Exception:
            pass

        print("="*60)
        print(f"URL: {url}")
        print(f"Saved → {raw_file.name}, {clean_file.name}")
        print(f"Title: {title}")
        print(f"Words: {len(cleaned.split())}")
        print("Preview:", preview(cleaned, 300))


if __name__ == "__main__":
    main()
