import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from src.db.logger import get_logger
from src.collectors.flashscore.config import resolve_bookmaker

logger = get_logger(__name__)

# Separador que o Flashscore usa no atributo title para indicar movimento de odd.
# Formato: "<abertura> » <fechamento>"  (U+00BB RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK)
_OPENING_SEPARATOR = '»'

# Padrões conhecidos que NÃO são bookmakers (filtrar)
_NOISE_PATTERNS = re.compile(
    r'livebet|livescore|advert|promo|banner|badge',
    re.IGNORECASE
)

def _log_unidentified_row(row):
    """
    Log de diagnóstico para rows que falham em todas as camadas da cascata.
    """
    try:
        snippet = str(row)[:300]
        logger.warning(f"Row sem bookmaker identificado | HTML snippet: {snippet}")
    except Exception:
        logger.warning("Row sem bookmaker identificado (não foi possível extrair snippet)")

def _extract_bookmaker_from_row(row) -> Optional[str]:
    """
    Tenta extrair o nome do bookmaker de uma row da tabela de odds.
    Usa cascata de 3 camadas, da mais estável à menos estável.
    """
    name = None

    # ── CAMADA 1: Seletor semântico por href (mais resistente) ──
    # Links para páginas de bookmaker contêm "/bookmaker/" no href
    link = row.find('a', href=lambda h: h and '/bookmaker/' in h)
    if link:
        name = link.get('title') or link.get_text(strip=True)
        if name and not _NOISE_PATTERNS.search(name):
            logger.debug(f"Bookmaker via href semântico: {name}")
            return name.strip()

    # ── CAMADA 2: Seletor clássico por classe CSS (fallback) ──
    # Pode voltar a funcionar se o Flashscore restaurar a classe
    link = row.find('a', class_=lambda c: c and 'oddsCell__bookmaker' in c)
    if link:
        name = link.get('title') or link.get_text(strip=True)
        if name and not _NOISE_PATTERNS.search(name):
            logger.debug(f"Bookmaker via classe CSS: {name}")
            return name.strip()

    # ── CAMADA 3: Busca por <img> com alt descritivo ──
    # Algumas variações do DOM usam só o ícone com alt text
    img = row.find('img', alt=True)
    if img:
        alt = img.get('alt', '').strip()
        if alt and not _NOISE_PATTERNS.search(alt):
            if resolve_bookmaker(alt) is not None:
                logger.debug(f"Bookmaker via img alt: {alt}")
                return alt

    return None


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
    Extrai o valor da linha (handicap/total) a partir da célula dedicada do Flashscore.
    Suporta seletores modernos (data-testid) e fallbacks legados.
    """
    # 1. Tentativa por data-testid (seletor moderno do Flashscore)
    cell = row.find(lambda tag: tag.get("data-testid") == "wcl-oddsCell")
    
    # 2. Tentativa por classe CSS específica (legado/fallback)
    if not cell:
        cell = row.find(
            lambda tag: tag.name in ("a", "div", "span")
            and tag.get("class")
            and any("handicap" in c.lower() for c in (tag.get("class") or []))
        )
        
    # 3. Fallback genérico para qualquer elemento de oddsCell que não seja link de odd/bookmaker
    if not cell:
        cell = row.find(
            lambda tag: tag.name in ("div", "span")
            and tag.get("class")
            and any("oddscell" in c.lower() for c in (tag.get("class") or []))
            and not any(x in "".join(tag.get("class")).lower() for x in ("oddscell__odd", "oddscellodd", "oddscell__bookmaker", "oddscellbookmaker"))
        )

    if cell:
        val_span = cell.find(lambda tag: tag.get("data-testid") == "wcl-oddsValue")
        raw = (val_span.get_text(strip=True) if val_span else cell.get_text(strip=True))
        
        # Caso especial: Flashscore exibe célula vazia para handicap 0
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
    def parse_odds_table(html: str, market_config: dict, bm_map: dict = None) -> tuple[List[Dict], Dict]:
        """
        Extrai as odds de uma aba de comparação de odds.
        Retorna (odds_entries, parsing_stats).
        """
        soup = BeautifulSoup(html, "html.parser")
        
        parsing_stats = {
            "unidentified_rows": 0,
            "unknown_bookmakers": set()
        }
        
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
        
        _unknown_bookmakers_in_batch = parsing_stats["unknown_bookmakers"]
        
        for index, row in enumerate(rows):
            if index == 0:
                logger.debug(f"FIRST ODDS ROW DOM:\n{row.prettify()}")
            
            # 1. Tenta identificar o bookmaker com a cascata
            raw_name = _extract_bookmaker_from_row(row)
            
            if raw_name is None:
                _log_unidentified_row(row)
                parsing_stats["unidentified_rows"] += 1
                continue
                
            our_bm_key = resolve_bookmaker(raw_name)
            if our_bm_key is None:
                if raw_name.lower() not in _unknown_bookmakers_in_batch:
                    _unknown_bookmakers_in_batch.add(raw_name.lower())
                    logger.warning(f"Bookmaker desconhecido: '{raw_name}'")
                continue
                
def _extract_cell_odds(cell) -> tuple[Optional[str], Optional[float]]:
    """
    Extrai o valor de FECHAMENTO (texto bruto da odd) e ABERTURA (float) de uma célula de odd.
    Suporta atributos 'title', 'data-title', 'data-tooltip' na célula ou em elementos filhos,
    além do separador '»' (U+00BB) para movimento de odds.
    
    Retorna: (closing_text, opening_val)
    """
    # 1. Extração do valor de FECHAMENTO (closing_text)
    closing_text = None
    
    # 1a. Tenta elementos com data-testid="wcl-oddsValue" (WCL moderno)
    val_node = cell.find(lambda tag: tag.get("data-testid") == "wcl-oddsValue")
    if val_node:
        t = val_node.get_text(strip=True)
        if t and (t == "-" or re.match(r'^\d+\.?\d*$', t)):
            closing_text = t
            
    # 1b. Tenta inner spans se ainda não encontrou
    if not closing_text:
        inner_spans = cell.find_all("span")
        for span in inner_spans:
            text = span.get_text(strip=True)
            if text and (text == "-" or re.match(r'^\d+\.?\d*$', text)):
                closing_text = text
                break

    # 1c. Fallback pro texto direto da célula
    if not closing_text:
        text = cell.get_text(strip=True)
        if text and (text == "-" or re.match(r'^\d+\.?\d*$', text)):
            closing_text = text
            
    # 2. Extração do valor de ABERTURA (opening_val)
    # Procura 'title', 'data-title', 'data-tooltip' na célula e nos seus filhos
    raw_title = ""
    for target in [cell] + list(cell.find_all(True)):
        t = target.get('title') or target.get('data-title') or target.get('data-tooltip') or ''
        if t and _OPENING_SEPARATOR in t:
            raw_title = t.strip()
            break
        elif t and not raw_title:
            raw_title = t.strip()

    opening_val = None
    if _OPENING_SEPARATOR in raw_title:
        opening_part = raw_title.split(_OPENING_SEPARATOR)[0].strip()
        try:
            opening_val = float(opening_part)
        except ValueError:
            opening_val = None
    else:
        if raw_title:
            try:
                opening_val = float(raw_title)
            except ValueError:
                pass
        if opening_val is None and closing_text and closing_text != "-":
            try:
                opening_val = float(closing_text)
            except ValueError:
                pass

    return closing_text, opening_val


def _find_odds_cells(row) -> List:
    """
    Busca todas as células de odds dentro de uma linha da tabela.
    Aplica estratégia de resiliência em 3 camadas (WCL data-testid, classes CSS legadas/modernas e fallback semântico).
    """
    # ── CAMADA 1: Seletores específicos por data-testid e classe CSS ──
    cells = row.find_all(
        lambda tag: tag.name in ("a", "div", "span", "td") and (
            # WCL data-testid
            (tag.get("data-testid") and "wcl-oddscell" in tag.get("data-testid").lower())
            or
            # Classes CSS (legadas + WCL)
            (tag.get("class") and any(
                x in " ".join(tag.get("class")).lower() 
                for x in ("oddscell__odd", "oddscellodd", "wcl-oddscell", "wcl-oddsvalue", "oddscell")
            ))
        )
    )

    filtered_cells = []
    for c in cells:
        # Se o elemento pai já é uma célula tratada, evita duplicar sub-elementos internos (ex: wcl-oddsValue dentro de wcl-oddsCell)
        if any(c in prev.descendants for prev in filtered_cells):
            continue
        
        c_class = " ".join(c.get("class") or []).lower()
        c_testid = (c.get("data-testid") or "").lower()
        href = (c.get("href") or "").lower()
        
        # Ignora se for link ou container de bookmaker
        if "/bookmaker/" in href or "bookmaker" in c_class or "bookmaker" in c_testid:
            continue
        # Ignora se for célula dedicada de handicap/total/linha
        if "handicap" in c_class or "handicap" in c_testid or "total" in c_class:
            continue
            
        filtered_cells.append(c)

    if filtered_cells:
        return filtered_cells

    # ── CAMADA 2: Fallback semântico por <a> tags na linha (excluindo bookmaker e handicap) ──
    a_tags = row.find_all("a")
    for a in a_tags:
        href = (a.get("href") or "").lower()
        a_class = " ".join(a.get("class") or []).lower()
        if "/bookmaker/" in href or "bookmaker" in a_class:
            continue
        if "handicap" in a_class:
            continue
        text = a.get_text(strip=True)
        if text and (text == "-" or re.search(r'\d+\.?\d*', text)):
            filtered_cells.append(a)

    return filtered_cells


class FlashscoreParser:
    """
    Parser para conteúdo HTML da página do Flashscore.
    Isola a manipulação de DOM/CSS que muda frequentemente.
    """
    
    @staticmethod
    def parse_odds_table(html: str, market_config: dict, bm_map: dict = None) -> tuple[List[Dict], Dict]:
        """
        Extrai as odds de uma aba de comparação de odds.
        Retorna (odds_entries, parsing_stats).
        """
        soup = BeautifulSoup(html, "html.parser")
        
        parsing_stats = {
            "unidentified_rows": 0,
            "unknown_bookmakers": set()
        }
        
        # Seletor específico para as linhas de bookmakers na tabela de odds
        # Confirmado no DOM real: div.ui-table__row contém bookmaker + odds cells
        rows = soup.find_all("div", class_="ui-table__row")
        
        if not rows:
            # Fallback: tenta seletor alternativo (incluindo data-testid moderno)
            rows = soup.find_all(
                lambda tag: tag.name == "div" and (
                    (tag.get("class") and any("oddsCell__bookmakerPart" in c for c in tag.get("class"))) or
                    (tag.get("data-testid") and "tablerow" in tag.get("data-testid").lower())
                )
            )
            if rows:
                rows = [r if "tablerow" in (r.get("data-testid") or "").lower() else r.parent for r in rows if r]
        
        if not rows:
            logger.debug(f"No odds rows found in HTML ({len(html)} bytes). Odds table may not have rendered.")
        
        results = []
        sys_market = market_config["sys_market"]
        period = market_config["period"]
        
        _unknown_bookmakers_in_batch = parsing_stats["unknown_bookmakers"]
        
        for index, row in enumerate(rows):
            if index == 0:
                logger.debug(f"FIRST ODDS ROW DOM:\n{row.prettify()}")
            
            # 1. Tenta identificar o bookmaker com a cascata
            raw_name = _extract_bookmaker_from_row(row)
            
            if raw_name is None:
                _log_unidentified_row(row)
                parsing_stats["unidentified_rows"] += 1
                continue
                
            our_bm_key = resolve_bookmaker(raw_name)
            if our_bm_key is None:
                if raw_name.lower() not in _unknown_bookmakers_in_batch:
                    _unknown_bookmakers_in_batch.add(raw_name.lower())
                    logger.warning(f"Bookmaker desconhecido: '{raw_name}'")
                continue
                
            # 2. Extrai os valores numéricos e odds de abertura da linha
            cells = _find_odds_cells(row)
            
            vals = []
            opening_vals = []
            for cell in cells:
                closing_text, opening_val = _extract_cell_odds(cell)
                vals.append(closing_text)
                opening_vals.append(opening_val)
            
            # Filtra vals para remover Nones e converter pra float
            parsed_vals = [float(v) if v and v != "-" else None for v in vals]
            parsed_vals = [v for v in parsed_vals if v is not None]
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
                            "odds_2": parsed_vals[2],
                            # Abertura: None se o title não tiver '»' (odd não se moveu)
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": opening_vals[1] if len(opening_vals) > 1 else None,
                            "opening_2": opening_vals[2] if len(opening_vals) > 2 else None,
                        })
                elif sys_market == "ou":
                    # Over/Under: Bookmaker | Total Line | Over | Under
                    # Extrai a linha (total) pela célula CSS dedicada
                    line_val = _extract_line_from_cell(row, signed=False)
                    
                    if len(parsed_vals) >= 2 and line_val is not None:
                        # Frequentemente, a própria linha parseou no parsed_vals. 
                        # Precisamos excluir a linha se ela foi detectada como odd acidentalmente.
                        real_odds = [v for v in parsed_vals if v != line_val]
                        # Se não sobrou 2 odds, fallback para pegar as últimas duas
                        if len(real_odds) < 2:
                            real_odds = parsed_vals[-2:]
                            
                        if len(real_odds) >= 2:
                            # Abertura: células 0=Over, 1=Under (mesma ordem que closing)
                            results.append({
                                "bookmaker": our_bm_key,
                                "market_type": "ou",
                                "period": period,
                                "line": line_val,
                                "odds_1": real_odds[0], # Over
                                "odds_x": None,
                                "odds_2": real_odds[1], # Under
                                "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                                "opening_x": None,
                                "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
                            })
                elif sys_market == "ah":
                    # Asian Handicap: Bookmaker | Handicap | ODD 1 | ODD 2
                    # Extrai a linha (handicap) pela célula CSS dedicada
                    line_val = _extract_line_from_cell(row, signed=True)
                    
                    # Fallback final para handicap 0:
                    # No Flashscore, quando o AH é 0 a célula oddsCell__handicap
                    # NÃO EXISTE no DOM (é removida, não apenas vazia).
                    # Se temos bookmaker + 2 odds mas nenhuma linha → é AH 0.
                    if line_val is None and len(parsed_vals) >= 2:
                        # Confirmar que realmente não há célula handicap na row
                        has_handicap_cell = row.find(
                            lambda tag: tag.get("class")
                            and any("handicap" in c.lower() for c in (tag.get("class") or []))
                        )
                        if not has_handicap_cell:
                            line_val = 0.0
                    
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
                            "odds_2": real_odds[1],
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": None,
                            "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
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
                            "odds_2": parsed_vals[2], # X2
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": opening_vals[1] if len(opening_vals) > 1 else None,
                            "opening_2": opening_vals[2] if len(opening_vals) > 2 else None,
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
                            "odds_2": parsed_vals[1], # 2
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": None,
                            "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
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
                            "odds_2": parsed_vals[1], # No
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": None,
                            "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
                        })
            except Exception as e:
                logger.debug(f"[FlashscoreParser] Ignorando row {bm_title} mal formatada: {e}")
                continue
                
        return results, parsing_stats

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
