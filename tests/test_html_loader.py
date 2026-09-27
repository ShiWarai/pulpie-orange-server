from app.html_loader import load_html


def test_load_html_string():
    html = "<html><body>hi</body></html>"
    assert load_html(html, "string", ssl_verify=True) == html


def test_load_html_file(tmp_path):
    p = tmp_path / "page.html"
    p.write_text("<p>x</p>", encoding="utf-8")
    assert "x" in load_html(str(p), "file", ssl_verify=True)
