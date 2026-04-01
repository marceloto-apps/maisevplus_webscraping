"""
T07 — Understat HTTP Scraper
Bate no front-end do understat.com, faz request GET tradicional
e decodifica variáveis inline JSON usando expressões regulares pesadas.
Sem uso de BS4 para evitar dependências lentas.
"""
import re
import json
import httpx
import logging
from typing import Optional

from ...db.logger import get_logger

logger = get_logger(__name__)

PATTERNS = {
    'shotsData': re.compile(
        r"var\s+shotsData\s*=\s*JSON\.parse\(\s*'(.+?)'\s*\)", re.DOTALL
    ),
    'shotsData_alt': re.compile(
        r"var\s+shotsData\s*=\s*(\{.+?\});", re.DOTALL
    ),
    'datesData': re.compile(
        r"var\s+datesData\s*=\s*JSON\.parse\(\s*'(.+?)'\s*\)", re.DOTALL
    ),
    'datesData_alt': re.compile(
        r"var\s+datesData\s*=\s*(\[.+?\]);", re.DOTALL
    ),
}

class UnderstatScraper:
    BASE_URL = "https://understat.com"

    def __init__(self):
        # Understat dropa requisicoes agressivas e s/ User-agent
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        )

    async def close(self):
        await self.client.aclose()

    def _extract_var(self, html: str, var_name: str) -> Optional[dict]:
        """ Tenta varrer de duas formas do HTML. """
        # Tenta JSON.parse primeiro
        pattern_parse = PATTERNS.get(var_name)
        if pattern_parse:
            m = pattern_parse.search(html)
            if m:
                raw_hex = m.group(1)
                try:
                    raw = raw_hex.encode('utf-8').decode('unicode_escape')
                    return json.loads(raw)
                except Exception as e:
                    logger.error("understat_json_parse_failed", var=var_name, error=str(e))
        
        # Fallback: atribuicao direta
        pattern_alt = PATTERNS.get(f'{var_name}_alt')
        if pattern_alt:
            m_alt = pattern_alt.search(html)
            if m_alt:
                try:
                    return json.loads(m_alt.group(1))
                except Exception as e:
                    logger.error("understat_json_alt_failed", var=var_name, error=str(e))
        
        logger.warning("understat_var_not_found", var=var_name)
        return None

    async def fetch_league_matches(self, league_name: str, season: str) -> Optional[list]:
        """
        Recupera as meta-informações de todos os matchs de uma liga.
        URL padrao: /league/{EPL}/{2023}
        """
        url = f"{self.BASE_URL}/league/{league_name}/{season}"
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            
            dates_data = self._extract_var(resp.text, 'datesData')
            # datesData costuma ser uma lista de objs match
            return dates_data if isinstance(dates_data, list) else []
            
        except httpx.HTTPError as e:
            logger.error("understat_html_scrap_failed", url=url, error=str(e))
            return None

    async def fetch_match_shots(self, understat_match_id: int) -> Optional[dict]:
        """
        No understat acessamos a url /match/1234
        Devolve shotsData contendo dict = {'h': [{...}, ...], 'a': [{...}]}
        """
        url = f"{self.BASE_URL}/match/{understat_match_id}"
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            
            return self._extract_var(resp.text, 'shotsData')
            
        except httpx.HTTPError as e:
            logger.error("understat_html_scrap_failed", url=url, error=str(e))
            return None
