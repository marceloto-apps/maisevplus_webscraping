import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from src.db.logger import get_logger

logger = get_logger(__name__)


def _parse_line_value(raw_text: str, signed: bool = False) -> Optional[float]:
    """
    Converte texto de linha (handicap/total) do Flashscore para float.
    
    Formatos suportados:
    - Inteiro: "3", "0", "-3", "+2"
    - Decimal: "2.5", "-0.5", "+1.5", "2.0"
    - Quarter-goal (comma-separated): "2, 2.5" → 2.25, "-3, -3.5" → -3.25
    
    Args:
        signed: Se True, aceita sinais +/- (para AH). Se False, só positivos (para OU).
    """
    text = raw_text.strip()
    if not text:
        return None
    
    # Caso 1: Quarter-goal (dois valores separados por vírgula)
    if ',' in text:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
                return round((v1 + v2) / 2, 2)  # média = quarter line
            except ValueError:
                pass
    
    # Caso 2: Valor único (inteiro ou decimal)
    pattern = r'^([+-]?\d+(?:\.\d+)?)$' if signed else r'^(\d+(?:\.\d+)?)$'
    match = re.match(pattern, text)
    if match:
        return float(match.group(1))
    
    return None


def _extract_line_from_cell(row, signed: bool = False) -> Optional[float]:
    """
    Extrai o valor da linha (handicap/total) a partir da célula CSS dedicada do Flashscore.
    
    O DOM do Flashscore usa a classe 'oddsCell__handicap' (ou variações) para a célula
    que contém exclusivamente o valor da linha, sem misturar com bookmaker ou odds.
    """
    # Tentativa 1: Classe CSS específica do Flashscore para a célula de handicap/total
    handicap_cell = row.find(
        lambda tag: tag.name in ("a", "div", "span")
        and tag.get("class")
        and any("handicap" in c.lower() for c in (tag.get("class") or []))
    )
    
    if handicap_cell:
        # Dentro da célula, o valor pode estar num span filho ou ser texto direto
        inner_span = handicap_cell.find("span")
        raw = (inner_span.get_text(strip=True) if inner_span else handicap_cell.get_text(strip=True))
        
        # Caso especial: Flashscore exibe célula vazia para handicap 0
        # A célula CSS existe mas não contém texto visível
        if not raw and signed:
            return 0.0
        
        val = _parse_line_value(raw, signed=signed)
        if val is not None:
            return val
    
    return None


def _parse_line_from_text(full_text: str, signed: bool = False) -> Optional[float]:
    """
    Fallback: extrai o valor da linha a partir do texto completo da row via regex.
    Mais frágil que _extract_line_from_cell() mas serve como backup.
    """
    # Tenta quarter-goal primeiro (ex: "-3, -3.5" ou "2, 2.5")
    if signed:
        qg_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)', full_text)
    else:
        qg_match = re.search(r'(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)', full_text)
    
    if qg_match:
        try:
            v1, v2 = float(qg_match.group(1)), float(qg_match.group(2))
            return round((v1 + v2) / 2, 2)
        except ValueError:
            pass
    
    # Tenta valor único (inteiro ou decimal)
    if signed:
        single_match = re.search(r'(?:^|\s)([+-]?\d+(?:\.\d+)?)(?:\s|$)', full_text)
    else:
        single_match = re.search(r'(?:^|\s)(\d+(?:\.\d+)?)(?:\s|$)', full_text)
    
    if single_match:
        return float(single_match.group(1))
    
    return None


def _is_valid_line(val: float) -> bool:
    """
    Valida se um valor parece ser uma linha AH/OU legítima.
    Linhas válidas são sempre múltiplos de 0.25: inteiros, .25, .5, .75.
    Valores como 1.16, 2.33, 4.35 são odds — não linhas.
    """
    remainder = abs(val) % 0.25
    return remainder < 0.001 or remainder > 0.249

class FlashscoreParser:
    """
    Parser para conteúdo HTML da página do Flashscore.
    Isola a manipulação de DOM/CSS que muda frequentemente.
    """
    
    @staticmethod
    def parse_odds_table(html: str, market_config: dict, bm_map: dict) -> List[Dict]:
        """
        Extrai as odds de uma aba de comparação de odds.
        Retorna uma lista contendo dicionários padronizados para o banco de dados.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Seletor específico para as linhas de bookmakers na tabela de odds
        # Confirmado no DOM real: div.ui-table__row contém bookmaker + odds cells
        rows = soup.find_all("div", class_="ui-table__row")
        
        if not rows:
            # Fallback: tenta seletor alternativo
            rows = soup.find_all("div", class_=lambda c: c and "oddsCell__bookmakerPart" in c)
            if rows:
                # Se achamos bookmakerPart, subimos pro parent (ui-table__row)
                rows = [r.parent for r in rows if r.parent]
        
        if not rows:
            logger.debug(f"No odds rows found in HTML ({len(html)} bytes). Odds table may not have rendered.")
        
        results = []
        sys_market = market_config["sys_market"]
        period = market_config["period"]
        
        for index, row in enumerate(rows):
            if index == 0:
                logger.debug(f"FIRST ODDS ROW DOM:\n{row.prettify()}")
            # 1. Tenta identificar o bookmaker
            bm_title = None
            bm_img = row.find("img")
            bm_link = row.find("a", title=True)
            
            if bm_img and bm_img.get("alt"):
                bm_title = bm_img.get("alt")
            elif bm_link and bm_link.get("title"):
                bm_title = bm_link.get("title")
                
            if not bm_title:
                continue
                
            our_bm_key = bm_map.get(bm_title)
            if not our_bm_key:
                if index < 3:  # Log apenas os primeiros para não poluir
                    logger.debug(f"[FlashscoreParser] Bookmaker '{bm_title}' não está no map, pulando")
                continue
                
            # 2. Extrai os valores numéricos da linha
            # Pega todas as <a> com classe oddsCell__odd
            cells = row.find_all("a", class_=lambda c: c and "oddsCell__odd" in c)
            
            vals = []
            for cell in cells:
                # O valor fica dentro de um <span> no link
                # Pega todos os spans e filtra o que parece ser um número decimal
                inner_spans = cell.find_all("span")
                for span in inner_spans:
                    text = span.get_text(strip=True)
                    if text and re.match(r'^\d+\.?\d*$', text):
                        vals.append(text)
                        break  # Pega só o primeiro span numérico de cada cell
            
            # Substitui "-" por None e converte pra float
            parsed_vals = [float(v) if v != "-" else None for v in vals if v]
            if not parsed_vals:
                continue
                
            # 3. Monta o Dicionário conforme o Mercado
            try:
                if sys_market == "1x2":
                    if len(parsed_vals) >= 3:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "1x2",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0],
                            "odds_x": parsed_vals[1],
                            "odds_2": parsed_vals[2]
                        })
                elif sys_market == "ou":
                    # Over/Under: Bookmaker | Total Line | Over | Under
                    # Extrai a linha (total) pela célula CSS dedicada
                    line_val = _extract_line_from_cell(row, signed=False)
                    
                    # Fallback: regex no texto completo da row
                    if line_val is None:
                        line_text = row.get_text(separator=' ', strip=True)
                        line_val = _parse_line_from_text(line_text, signed=False)
                        # Validar que o fallback não pegou uma odd como linha
                        if line_val is not None and not _is_valid_line(line_val):
                            line_val = None
                    
                    if len(parsed_vals) >= 2 and line_val is not None:
                        # Frequentemente, a própria linha parseou no parsed_vals. 
                        # Precisamos excluir a linha se ela foi detectada como odd acidentalmente.
                        real_odds = [v for v in parsed_vals if v != line_val]
                        # Se não sobrou 2 odds, fallback para pegar as últimas duas
                        if len(real_odds) < 2:
                            real_odds = parsed_vals[-2:]
                            
                        if len(real_odds) >= 2:
                            results.append({
                                "bookmaker": our_bm_key,
                                "market_type": "ou",
                                "period": period,
                                "line": line_val,
                                "odds_1": real_odds[0], # Over
                                "odds_x": None,
                                "odds_2": real_odds[1]  # Under
                            })
                elif sys_market == "ah":
                    # Asian Handicap: Bookmaker | Handicap | ODD 1 | ODD 2
                    # Extrai a linha (handicap) pela célula CSS dedicada
                    line_val = _extract_line_from_cell(row, signed=True)
                    
                    # Fallback: regex no texto completo da row
                    if line_val is None:
                        line_text = row.get_text(separator=' ', strip=True)
                        line_val = _parse_line_from_text(line_text, signed=True)
                        # Validar que o fallback não pegou uma odd como linha
                        if line_val is not None and not _is_valid_line(line_val):
                            line_val = None
                    
                    # As odds geralmente são as últimas duas colunas da row
                    if line_val is not None and len(parsed_vals) >= 2:
                        # odds1 = home, odds2 = away
                        real_odds = parsed_vals[-2:] 
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "ah",
                            "period": period,
                            "line": line_val,
                            "odds_1": real_odds[0],
                            "odds_x": None,
                            "odds_2": real_odds[1]
                        })
                elif sys_market == "dc":
                    # Double Chance: 1X | 12 | X2
                    if len(parsed_vals) >= 3:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "dc",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0], # 1X
                            "odds_x": parsed_vals[1], # 12
                            "odds_2": parsed_vals[2]  # X2
                        })
                elif sys_market == "dnb":
                    # Draw No Bet: 1 | 2
                    if len(parsed_vals) >= 2:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "dnb",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0], # 1
                            "odds_x": None,
                            "odds_2": parsed_vals[1]  # 2
                        })
                elif sys_market == "btts":
                    # Both Teams To Score: Yes | No
                    if len(parsed_vals) >= 2:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "btts",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0], # Yes
                            "odds_x": None,
                            "odds_2": parsed_vals[1]  # No
                        })
            except Exception as e:
                logger.debug(f"[FlashscoreParser] Ignorando row {bm_title} mal formatada: {e}")
                continue
                
        return results

    @staticmethod
    def extract_match_ids_from_schedule(html: str) -> List[str]:
        """
        No DOM da página de schedule/results de uma liga, extrai os IDs dos matches.
        """
        import re
        # O flashscore injeta IDs nos elementos class="event__match"
        # Ou diretamente em URLs href="/match/XXXXXXX/"
        ids = list(set(re.findall(r'/match/([A-Za-z0-9]{8,})/?', html)))
        return ids
