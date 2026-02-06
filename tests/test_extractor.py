"""Tests for the full-text article extractor."""

import pytest
from app.fetchers.extractor import extract_article_text, ExtractionResult


class TestExtractArticleText:
    def test_extract_from_article_tag(self):
        html = """
        <html><body>
            <nav>Navigation stuff</nav>
            <article>
                <h1>Big News</h1>
                <p>This is the first paragraph of a real article.</p>
                <p>This is the second paragraph with more details.</p>
            </article>
            <footer>Footer stuff</footer>
        </body></html>
        """
        text = extract_article_text(html)
        assert "first paragraph" in text
        assert "second paragraph" in text
        assert "Navigation stuff" not in text
        assert "Footer stuff" not in text

    def test_extract_from_div_with_content_class(self):
        html = """
        <html><body>
            <div class="sidebar">Sidebar</div>
            <div class="article-content">
                <p>Article body text here with lots of words to score well.</p>
                <p>More article content for the reader to enjoy and learn from.</p>
            </div>
        </body></html>
        """
        text = extract_article_text(html)
        assert "Article body text" in text

    def test_extract_strips_scripts_and_styles(self):
        html = """
        <html><body>
            <script>var x = 1;</script>
            <style>.foo { color: red; }</style>
            <article>
                <p>Clean article text without scripts.</p>
            </article>
        </body></html>
        """
        text = extract_article_text(html)
        assert "Clean article text" in text
        assert "var x" not in text
        assert ".foo" not in text

    def test_extract_empty_html(self):
        text = extract_article_text("")
        assert text == ""

    def test_extract_minimal_html(self):
        html = "<html><body><p>Hello world</p></body></html>"
        text = extract_article_text(html)
        assert "Hello world" in text

    def test_extract_removes_nav_and_footer(self):
        html = """
        <html><body>
            <header><p>Header content</p></header>
            <nav><p>Nav links</p></nav>
            <main>
                <p>Main article content paragraph one.</p>
                <p>Main article content paragraph two.</p>
            </main>
            <aside><p>Sidebar widget</p></aside>
            <footer><p>Copyright notice</p></footer>
        </body></html>
        """
        text = extract_article_text(html)
        assert "Main article content" in text


class TestExtractionResult:
    def test_success_result(self):
        result = ExtractionResult(text="Article text", success=True, word_count=50)
        assert result.success is True
        assert result.word_count == 50
        assert result.error is None

    def test_failure_result(self):
        result = ExtractionResult(text="", success=False, error="Connection refused")
        assert result.success is False
        assert result.error == "Connection refused"
