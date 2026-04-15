"""
Testes unitários para _parse_line_value, _extract_line_from_cell e parse_odds_table
com foco em linhas inteiras, decimais e quarter-goal para AH e OU.
"""
import pytest
from bs4 import BeautifulSoup

from src.collectors.flashscore.parser import (
    _parse_line_value,
    _extract_line_from_cell,
    _parse_line_from_text,
    FlashscoreParser,
)


# ============================================================
# Testes para _parse_line_value
# ============================================================

class TestParseLineValue:
    """Testa parsing de valor de linha isolado."""

    # --- OU (unsigned) ---
    @pytest.mark.parametrize("text, expected", [
        ("2.5", 2.5),
        ("0.5", 0.5),
        ("1.5", 1.5),
        ("3.5", 3.5),
    ])
    def test_ou_half_lines(self, text, expected):
        assert _parse_line_value(text, signed=False) == expected

    @pytest.mark.parametrize("text, expected", [
        ("1", 1.0),
        ("2", 2.0),
        ("3", 3.0),
        ("0", 0.0),
    ])
    def test_ou_integer_lines(self, text, expected):
        assert _parse_line_value(text, signed=False) == expected

    @pytest.mark.parametrize("text, expected", [
        ("2, 2.5", 2.25),
        ("2.5, 3", 2.75),
        ("3.5, 4", 3.75),
        ("0.5, 1", 0.75),
        ("1, 1.5", 1.25),
    ])
    def test_ou_quarter_lines(self, text, expected):
        assert _parse_line_value(text, signed=False) == expected

    # --- AH (signed) ---
    @pytest.mark.parametrize("text, expected", [
        ("-0.5", -0.5),
        ("+1.5", 1.5),
        ("-2.5", -2.5),
        ("0.5", 0.5),
    ])
    def test_ah_half_lines(self, text, expected):
        assert _parse_line_value(text, signed=True) == expected

    @pytest.mark.parametrize("text, expected", [
        ("-3", -3.0),
        ("+2", 2.0),
        ("0", 0.0),
        ("-1", -1.0),
    ])
    def test_ah_integer_lines(self, text, expected):
        assert _parse_line_value(text, signed=True) == expected

    @pytest.mark.parametrize("text, expected", [
        ("-3, -3.5", -3.25),
        ("-0.5, 0", -0.25),
        ("0, -0.5", -0.25),
        ("1.5, 2", 1.75),
        ("-2, -2.5", -2.25),
        ("+0.5, +1", 0.75),
    ])
    def test_ah_quarter_lines(self, text, expected):
        assert _parse_line_value(text, signed=True) == expected

    # --- Edge cases ---
    def test_empty_string(self):
        assert _parse_line_value("", signed=False) is None
        assert _parse_line_value("", signed=True) is None

    def test_whitespace_only(self):
        assert _parse_line_value("   ", signed=False) is None

    def test_garbage(self):
        assert _parse_line_value("abc", signed=False) is None
        assert _parse_line_value("bet365", signed=True) is None

    def test_leading_trailing_whitespace(self):
        assert _parse_line_value("  2.5  ", signed=False) == 2.5
        assert _parse_line_value("  -3, -3.5  ", signed=True) == -3.25


# ============================================================
# Testes para _extract_line_from_cell
# ============================================================

class TestExtractLineFromCell:
    """Testa extração da linha via classe CSS oddsCell__handicap."""

    def _make_row(self, handicap_text, market="ah"):
        """Cria um HTML simulando uma row do Flashscore com a célula handicap."""
        html = f"""
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="oddsCell__handicap">
                <span>{handicap_text}</span>
            </div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        return soup.find("div", class_="ui-table__row")

    def test_ah_integer_line(self):
        row = self._make_row("-3")
        assert _extract_line_from_cell(row, signed=True) == -3.0

    def test_ah_zero_line(self):
        row = self._make_row("0")
        assert _extract_line_from_cell(row, signed=True) == 0.0

    def test_ah_quarter_line(self):
        row = self._make_row("-3, -3.5")
        assert _extract_line_from_cell(row, signed=True) == -3.25

    def test_ah_half_line(self):
        row = self._make_row("-0.5")
        assert _extract_line_from_cell(row, signed=True) == -0.5

    def test_ou_integer_line(self):
        row = self._make_row("2")
        assert _extract_line_from_cell(row, signed=False) == 2.0

    def test_ou_quarter_line(self):
        row = self._make_row("2, 2.5")
        assert _extract_line_from_cell(row, signed=False) == 2.25

    def test_no_handicap_cell_returns_none(self):
        """Se a row não tiver a classe handicap, deve retornar None."""
        html = """
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("div", class_="ui-table__row")
        assert _extract_line_from_cell(row, signed=True) is None

    def test_ah_empty_cell_means_zero(self):
        """Flashscore exibe célula vazia (sem texto) para handicap 0."""
        html = """
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="oddsCell__handicap">
                <span></span>
            </div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("div", class_="ui-table__row")
        assert _extract_line_from_cell(row, signed=True) == 0.0

    def test_ah_empty_cell_no_span_means_zero(self):
        """DOM real confirmado: célula vazia SEM span para handicap 0."""
        html = """
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="ui-table__cell oddsCell__handicap"></div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("div", class_="ui-table__row")
        assert _extract_line_from_cell(row, signed=True) == 0.0

    def test_ah_text_direct_in_cell_no_span(self):
        """DOM real: valor direto no div sem span wrapper."""
        html = """
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="ui-table__cell oddsCell__handicap">-1</div>
            <a class="oddsCell__odd"><span>2.30</span></a>
            <a class="oddsCell__odd"><span>1.60</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("div", class_="ui-table__row")
        assert _extract_line_from_cell(row, signed=True) == -1.0

    def test_ah_quarter_direct_in_cell_no_span(self):
        """DOM real: quarter-goal direto no div sem span wrapper."""
        html = """
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="ui-table__cell oddsCell__handicap">-0.5, -1</div>
            <a class="oddsCell__odd"><span>4.35</span></a>
            <a class="oddsCell__odd"><span>1.21</span></a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        row = soup.find("div", class_="ui-table__row")
        assert _extract_line_from_cell(row, signed=True) == -0.75


# ============================================================
# Testes para _parse_line_from_text (fallback)
# ============================================================

class TestParseLineFromText:
    """Testa fallback de regex no texto completo."""

    def test_ah_quarter_in_text(self):
        text = "bet365 -3, -3.5 1.90 2.00"
        assert _parse_line_from_text(text, signed=True) == -3.25

    def test_ah_integer_in_text(self):
        text = "bet365 -3 1.90 2.00"
        assert _parse_line_from_text(text, signed=True) == -3.0

    def test_ou_integer_in_text(self):
        text = "bet365 2 1.90 2.00"
        assert _parse_line_from_text(text, signed=False) == 2.0

    def test_ou_quarter_in_text(self):
        text = "bet365 2, 2.5 1.90 2.00"
        assert _parse_line_from_text(text, signed=False) == 2.25


# ============================================================
# Testes integrados: parse_odds_table
# ============================================================

BM_MAP = {"bet365": "bet365", "Betano.br": "betano"}


class TestParseOddsTableAH:
    """Testa parse_odds_table para mercado Asian Handicap com vários formatos de linha."""

    def _html_ah_row(self, handicap_text):
        return f"""
        <html><body>
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="oddsCell__handicap">
                <span>{handicap_text}</span>
            </div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        </body></html>
        """

    def test_integer_line(self):
        html = self._html_ah_row("-3")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == -3.0
        assert result[0]["odds_1"] == 1.90
        assert result[0]["odds_2"] == 2.00

    def test_zero_line(self):
        html = self._html_ah_row("0")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 0.0

    def test_positive_integer_line(self):
        html = self._html_ah_row("+2")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 2.0

    def test_quarter_line(self):
        html = self._html_ah_row("-3, -3.5")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == -3.25

    def test_half_line(self):
        html = self._html_ah_row("-0.5")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == -0.5

    def test_quarter_line_negative_zero(self):
        html = self._html_ah_row("-0.5, 0")
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == -0.25

    def test_empty_cell_means_zero(self):
        """AH 0: Flashscore exibe célula existente mas vazia."""
        html = """
        <html><body>
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="oddsCell__handicap">
                <span></span>
            </div>
            <a class="oddsCell__odd"><span>1.90</span></a>
            <a class="oddsCell__odd"><span>2.00</span></a>
        </div>
        </body></html>
        """
        config = {"sys_market": "ah", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 0.0
        assert result[0]["odds_1"] == 1.90
        assert result[0]["odds_2"] == 2.00

class TestParseOddsTableOU:
    """Testa parse_odds_table para mercado Over/Under com vários formatos de linha."""

    def _html_ou_row(self, line_text):
        return f"""
        <html><body>
        <div class="ui-table__row">
            <div class="oddsCell__bookmakerPart">
                <a title="bet365"><img alt="bet365"/></a>
            </div>
            <div class="oddsCell__handicap">
                <span>{line_text}</span>
            </div>
            <a class="oddsCell__odd"><span>1.85</span></a>
            <a class="oddsCell__odd"><span>2.05</span></a>
        </div>
        </body></html>
        """

    def test_half_line(self):
        html = self._html_ou_row("2.5")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 2.5
        assert result[0]["odds_1"] == 1.85
        assert result[0]["odds_2"] == 2.05

    def test_integer_line(self):
        html = self._html_ou_row("2")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 2.0

    def test_integer_line_one(self):
        html = self._html_ou_row("1")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 1.0

    def test_integer_line_three(self):
        html = self._html_ou_row("3")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 3.0

    def test_quarter_line(self):
        html = self._html_ou_row("2, 2.5")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 2.25

    def test_quarter_line_high(self):
        html = self._html_ou_row("3.5, 4")
        config = {"sys_market": "ou", "period": "ft"}
        result = FlashscoreParser.parse_odds_table(html, config, BM_MAP)
        assert len(result) == 1
        assert result[0]["line"] == 3.75
