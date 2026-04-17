from __future__ import annotations

from miroworld.services.scrape_service import ScrapeService


def test_extract_prefers_article_body_and_drops_page_chrome() -> None:
    service = ScrapeService()
    html = """
    <html>
      <head><title>Michigan Elections FAQ</title></head>
      <body>
        <header>Donate now to support local journalism</header>
        <nav>Home Politics Elections Newsletter</nav>
        <main>
          <article>
            <h1>Where Trump and Harris stand on immigration</h1>
            <p>Trump proposes mass deportations and expanded detention near the southern border.</p>
            <p>Harris supports a bipartisan border package and expanded legal pathways for asylum review.</p>
          </article>
        </main>
        <aside>Share this story on Facebook</aside>
        <footer>Republish this article | Contact us | Privacy policy</footer>
      </body>
    </html>
    """

    payload = service._extract(html, "https://example.com/politics")

    assert payload["title"] == "Michigan Elections FAQ"
    assert "mass deportations" in payload["text"]
    assert "bipartisan border package" in payload["text"]
    assert "Donate now" not in payload["text"]
    assert "Share this story" not in payload["text"]
    assert "Republish this article" not in payload["text"]


def test_extract_falls_back_to_largest_content_block_when_article_missing() -> None:
    service = ScrapeService()
    html = """
    <html>
      <head><title>Policy Updates</title></head>
      <body>
        <div class="promo">Subscribe for updates</div>
        <div class="story-body">
          <p>The state senate approved a property tax rebate for low-income households.</p>
          <p>The proposal would fund the rebate through a temporary surcharge on luxury real estate transfers.</p>
        </div>
        <div class="related-links">Related: sports | weather</div>
      </body>
    </html>
    """

    payload = service._extract(html, "https://example.com/taxes")

    assert "property tax rebate" in payload["text"]
    assert "luxury real estate transfers" in payload["text"]
    assert "Subscribe for updates" not in payload["text"]
    assert "sports | weather" not in payload["text"]


def test_extract_soup_text_skips_nodes_with_missing_attrs() -> None:
    service = ScrapeService()

    class BrokenTag:
        attrs = None

        def decompose(self) -> None:
            return None

        def find_all(self, selector, recursive=True):  # noqa: ANN001
            del selector, recursive
            return []

        def get_text(self, separator=" ", strip=True):  # noqa: ANN001
            del separator, strip
            return ""

        def get(self, key, default=None):  # noqa: ANN001
            del key, default
            raise AssertionError("BrokenTag.get should not be called when attrs are missing")

    class FallbackBody:
        def get_text(self, separator=" ", strip=True):  # noqa: ANN001
            del separator, strip
            return "Fallback policy body"

    class FakeSoup:
        body = FallbackBody()

        def find_all(self, selector):  # noqa: ANN001
            if selector == service._NOISE_TAGS:
                return []
            return [BrokenTag()]

        def select_one(self, selector):  # noqa: ANN001
            del selector
            return None

    assert service._extract_soup_text(FakeSoup()) == "Fallback policy body"


def test_extract_does_not_drop_body_for_modifier_classes_like_has_sidebar() -> None:
    service = ScrapeService()
    html = """
    <html>
      <head><title>Election Guide</title></head>
      <body class="has-sidebar single-post">
        <article>
          <p>Trump and Harris describe different immigration and health care priorities.</p>
          <p>Michigan voters are weighing the costs of drug prices and insurance premiums.</p>
        </article>
      </body>
    </html>
    """

    payload = service._extract(html, "https://example.com/guide")

    assert "different immigration and health care priorities" in payload["text"]
    assert "Michigan voters are weighing" in payload["text"]
