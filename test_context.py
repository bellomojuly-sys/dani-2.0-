"""Her life context page (D2-058): refresh, keep the last good text, combine."""

from context import LifeContext, combine


def test_refresh_reads_the_page_and_a_failure_keeps_the_last_good_text():
    pages = iter(["  Regole: niente domenica  ", RuntimeError("Notion could not be reached")])

    def fetch():
        value = next(pages)
        if isinstance(value, Exception):
            raise value
        return value

    life = LifeContext(fetch)
    assert life.refresh() is True and life.current() == "Regole: niente domenica"
    assert life.refresh() is False
    assert life.current() == "Regole: niente domenica" and "could not be reached" in life.error


def test_combine_puts_the_life_page_first_and_skips_empty_parts():
    both = combine("Obiettivi 2027", "Oggi sono stanca")
    assert both.index("Obiettivi 2027") < both.index("Oggi sono stanca")
    assert "her Notion page" in both and "Settings" in both
    assert "Settings" not in combine("Obiettivi", "  ")
    assert combine("", "") == ""


def test_the_character_page_comes_before_the_life_page():
    text = combine("Obiettivi 2027", "stanca", character="Dani è una donna, diretta")
    assert text.index("Dani è una donna") < text.index("Obiettivi 2027") < text.index("stanca")
    assert "Dani — chi è Dani" in text
