"""Unit tests for OCR module."""

from src.ocr import get_tesseract_language


class TestGetTesseractLanguage:
    """Tests for get_tesseract_language function."""

    def test_english_returns_eng(self):
        """Test that 'eng' returns 'eng'."""
        assert get_tesseract_language("eng") == "eng"

    def test_french_returns_fra(self):
        """Test that 'fra' returns 'fra'."""
        assert get_tesseract_language("fra") == "fra"

    def test_french_bibliographic_returns_fra(self):
        """Test that 'fre' (bibliographic code) also returns 'fra'."""
        assert get_tesseract_language("fre") == "fra"

    def test_german_returns_ger(self):
        """Test that 'deu' maps to 'ger' (Tesseract uses 'ger')."""
        assert get_tesseract_language("deu") == "ger"

    def test_spanish_returns_spa(self):
        """Test that 'spa' returns 'spa'."""
        assert get_tesseract_language("spa") == "spa"

    def test_italian_returns_ita(self):
        """Test that 'ita' returns 'ita'."""
        assert get_tesseract_language("ita") == "ita"

    def test_chinese_returns_none_not_installed(self):
        """Test that 'chi' or 'zho' returns None (not installed)."""
        assert get_tesseract_language("chi") is None
        assert get_tesseract_language("zho") is None

    def test_chinese_traditional_returns_none_not_installed(self):
        """Test that 'chi_tra' returns None (not installed)."""
        assert get_tesseract_language("chi_tra") is None

    def test_case_insensitive(self):
        """Test that language codes are case insensitive."""
        assert get_tesseract_language("ENG") == "eng"
        assert get_tesseract_language("Fra") == "fra"
        assert get_tesseract_language("DEU") == "ger"
        assert get_tesseract_language("SPA") == "spa"
        assert get_tesseract_language("ITA") == "ita"

    def test_none_returns_none(self):
        """Test that None returns None (skip OCR)."""
        assert get_tesseract_language(None) is None

    def test_empty_string_returns_none(self):
        """Test that empty string returns None (skip OCR)."""
        assert get_tesseract_language("") is None

    def test_unknown_language_returns_none(self):
        """Test that unknown language codes return None (skip OCR)."""
        assert get_tesseract_language("xyz") is None
        assert get_tesseract_language("abc") is None

    def test_dutch_returns_none_not_installed(self):
        """Test that 'dut' or 'nld' returns None (not installed)."""
        assert get_tesseract_language("dut") is None
        assert get_tesseract_language("nld") is None

    def test_czech_returns_none_not_installed(self):
        """Test that 'ces' or 'cze' returns None (not installed)."""
        assert get_tesseract_language("ces") is None
        assert get_tesseract_language("cze") is None

    def test_greek_returns_none_not_installed(self):
        """Test that 'gre' or 'ell' returns None (not installed)."""
        assert get_tesseract_language("gre") is None
        assert get_tesseract_language("ell") is None

    def test_portuguese_returns_none_not_installed(self):
        """Test that 'por' returns None (not installed)."""
        assert get_tesseract_language("por") is None

    def test_russian_returns_none_not_installed(self):
        """Test that 'rus' returns None (not installed)."""
        assert get_tesseract_language("rus") is None

    def test_japanese_returns_none_not_installed(self):
        """Test that 'jpn' returns None (not installed)."""
        assert get_tesseract_language("jpn") is None

    def test_korean_returns_none_not_installed(self):
        """Test that 'kor' returns None (not installed)."""
        assert get_tesseract_language("kor") is None


class TestInstalledLanguages:
    """Tests to verify only installed languages are supported."""

    def test_installed_languages(self):
        """Test that only installed languages return valid Tesseract codes."""
        from src.ocr import INSTALLED_TESSERACT_LANGUAGES

        installed_languages = [
            ("eng", "eng"),
            ("fra", "fra"),
            ("fre", "fra"),
            ("deu", "ger"),
            ("spa", "spa"),
            ("ita", "ita"),
        ]
        for iso_code, expected_tesseract in installed_languages:
            assert get_tesseract_language(iso_code) == expected_tesseract
            assert expected_tesseract in INSTALLED_TESSERACT_LANGUAGES
