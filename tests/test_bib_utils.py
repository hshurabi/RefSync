from refsync.bib_utils import safe_bib_key

def test_safe_bib_key_minimal():
    key = safe_bib_key({"author":"Doe, John", "year":"2024", "title":"Hello World"})
    assert "Doe2024Hello" in key
