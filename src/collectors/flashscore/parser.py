import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from src.db.logger import get_logger
from src.collectors.flashscore.config import resolve_bookmaker

logger = get_logger(__name__)

# Separador que o Flashscore usa no atributo title para indicar movimento de odd.
# Formato: "<abertura> » <fechamento>" (U+00BB RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK)
_OPENING_SEPARATOR = '»'

# Padrões conhecidos que NÃO são bookmakers (filtrar)
_NOISE_PATTERNS = re.compile(
    r'livebet|livescore|advert|promo|banner|badge',
    re.IGNORECASE
)

# Mapeamento de IDs numéricos de analytics do Flashscore WCL para os nossos nomes de bookmakers
_FLASHSCORE_NUMERIC_BM_MAP = {
    "141": "bet365",
    "16": "bet365",
    "160": "betano",
    "574": "betano",
    "264": "pinnacle",
    "4": "betfair_ex",
    "2": "1xbet",
    "1157": "1xbet",
    "833": "estrela_bet",
    "933": "superbet",
    "863": "betesporte",
    "959": "esportivabet",
    "995": "betnacional",
    "1047": "goldebet",
    "943": "betboom",
    "1069": "bet7k",
    "953": "f12",
    "12": "bwin",
    "3": "williamhill",
    "8": "unibet",
    "15": "888sport",
}

def _log_unidentified_row(row):
    """Log de diagnóstico para rows que falham em todas as camadas da cascata."""
    try:
        snippet = str(row)[:300]
        logger.warning(f"Row sem bookmaker identificado | HTML snippet: {snippet}")
    except Exception:
        logger.warning("Row sem bookmaker identificado (não foi possível extrair snippet)")

def _extract_bookmaker_from_row(row) -> Optional[str]:
    """
    Tenta extrair o nome do bookmaker de uma row da tabela de odds.
    Usa cascata de 4 camadas:
    1. href semântico (/bookmaker/...)
    2. Atributos WCL analytics (data-analytics-bookmaker-id / data-analytics-aff-id)
    3. Seletor clássico por classe/testid CSS
    4. Tag <img> com alt text descritivo
    """
    # ── CAMADA 1: Seletor semântico por href (/bookmaker/...) ──
    link = row.find('a', href=lambda h: h and '/bookmaker/' in h)
    if link:
        name = link.get('title') or link.get_text(strip=True)
        if name and not _NOISE_PATTERNS.search(name):
            logger.debug(f"Bookmaker via href semântico: {name}")
            return name.strip()

    # ── CAMADA 2: Atributos WCL Analytics (data-analytics-bookmaker-id / data-analytics-aff-id) ──
    bm_cell = row.find(lambda tag: tag.get("data-analytics-bookmaker-id") or tag.get("data-analytics-aff-id"))
    if bm_cell:
        bm_id = bm_cell.get("data-analytics-bookmaker-id")
        if not bm_id and bm_cell.get("data-analytics-aff-id"):
            aff = bm_cell.get("data-analytics-aff-id")
            m = re.search(r'^b(\d+)_', aff)
            if m:
                bm_id = m.group(1)
        if bm_id and bm_id in _FLASHSCORE_NUMERIC_BM_MAP:
            logger.debug(f"Bookmaker via WCL Analytics ID ({bm_id}): {_FLASHSCORE_NUMERIC_BM_MAP[bm_id]}")
            return _FLASHSCORE_NUMERIC_BM_MAP[bm_id]

    # ── CAMADA 3: Seletor por classe CSS / data-testid com title ou text ──
    link = row.find(lambda tag: tag.name in ("a", "div", "button") and (
        (tag.get("class") and any("bookmaker" in c.lower() for c in tag.get("class"))) or
        (tag.get("data-testid") and "bookmaker" in tag.get("data-testid").lower())
    ))
    if link:
        name = link.get('title') or link.get_text(strip=True)
        if name and not _NOISE_PATTERNS.search(name):
            logger.debug(f"Bookmaker via classe/testid CSS: {name}")
            return name.strip()

    # ── CAMADA 4: Busca por <img> com alt ou title descritivo ──
    img = row.find('img')
    if img:
        alt = img.get('alt', '').strip() or img.get('title', '').strip()
        if alt and not _NOISE_PATTERNS.search(alt):
            logger.debug(f"Bookmaker via img alt/title: {alt}")
            return alt

    # ── CAMADA 5: Se houver bm_id na WCL, usa bm_<id> ──
    bm_cell = row.find(lambda tag: tag.get("data-analytics-bookmaker-id") or tag.get("data-analytics-aff-id"))
    if bm_cell:
        bm_id = bm_cell.get("data-analytics-bookmaker-id")
        if not bm_id and bm_cell.get("data-analytics-aff-id"):
            m = re.search(r'^b(\d+)_', bm_cell.get("data-analytics-aff-id"))
            if m:
                bm_id = m.group(1)
        if bm_id:
            logger.debug(f"Bookmaker via WCL Analytics ID fallback: bm_{bm_id}")
            return f"bm_{bm_id}"

    return None


def _parse_line_value(raw_text: str, signed: bool = False) -> Optional[float]:
    """Converte texto de linha (handicap/total) do Flashscore para float."""
    text = raw_text.strip()
    if not text:
        return None
    
    if ',' in text:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) == 2:
            try:
                v1, v2 = float(parts[0]), float(parts[1])
                return round((v1 + v2) / 2, 2)
            except ValueError:
                pass
    
    pattern = r'^([+-]?\d+(?:\.\d+)?)$' if signed else r'^(\d+(?:\.\d+)?)$'
    match = re.match(pattern, text)
    if match:
        return float(match.group(1))
    
    return None


def _extract_line_from_cell(row, signed: bool = False) -> Optional[float]:
    """Extrai o valor da linha (handicap/total) a partir da célula dedicada do Flashscore."""
    cell = row.find(lambda tag: tag.get("data-testid") == "wcl-oddsCell" and "handicap" in (tag.get("class") or []))
    if not cell:
        cell = row.find(
            lambda tag: tag.name in ("a", "div", "span")
            and tag.get("class")
            and any("handicap" in c.lower() for c in (tag.get("class") or []))
        )
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
        
        if not raw and signed:
            return 0.0
        
        val = _parse_line_value(raw, signed=signed)
        if val is not None:
            return val
    
    return None


def _parse_line_from_text(full_text: str, signed: bool = False) -> Optional[float]:
    """Fallback: extrai o valor da linha a partir do texto completo da row via regex."""
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
    
    if signed:
        single_match = re.search(r'(?:^|\s)([+-]?\d+(?:\.\d+)?)(?:\s|$)', full_text)
    else:
        single_match = re.search(r'(?:^|\s)(\d+(?:\.\d+)?)(?:\s|$)', full_text)
    
    if single_match:
        return float(single_match.group(1))
    
    return None


def _is_valid_line(val: float) -> bool:
    """Valida se um valor parece ser uma linha AH/OU legítima."""
    remainder = abs(val) % 0.25
    return remainder < 0.001 or remainder > 0.249


def _extract_cell_odds(cell) -> tuple[Optional[str], Optional[float]]:
    """
    Extrai o valor de FECHAMENTO (texto bruto da odd) e ABERTURA (float) de uma célula de odd.
    Suporta atributos 'title', 'data-title', 'data-tooltip', 'aria-label' na célula ou elementos filhos.
    """
    closing_text = None
    
    # 1. Buscar valor de fechamento via regex no texto da célula
    raw_text = cell.get_text(strip=True).replace(",", ".").strip()
    match = re.search(r'\d+\.\d+|\d+', raw_text)
    if match:
        closing_text = match.group(0)
    elif "-" in raw_text:
        closing_text = "-"
            
    # 2. Buscar valor de abertura nos atributos title / tooltip / aria-label
    raw_title = ""
    for target in [cell] + list(cell.find_all(True)):
        t = target.get('title') or target.get('data-title') or target.get('data-tooltip') or ''
        if t:
            if "»" in t or ">" in t or _OPENING_SEPARATOR in t:
                raw_title = t.strip()
                break
            elif re.search(r'\d+\.\d+', t) and not any(x in t.lower() for x in ("bet", "1x", "kto", "win", "365", "logo")):
                raw_title = t.strip()

    opening_val = None
    if raw_title:
        if "»" in raw_title or ">" in raw_title or _OPENING_SEPARATOR in raw_title:
            parts = re.split(r'»|>|' + re.escape(_OPENING_SEPARATOR), raw_title)
            if parts and parts[0].strip():
                m_open = re.search(r'\d+\.\d+|\d+', parts[0].strip().replace(",", "."))
                if m_open:
                    try:
                        opening_val = float(m_open.group(0))
                    except ValueError:
                        pass
        else:
            nums = re.findall(r'\d+\.\d+', raw_title.replace(",", "."))
            if nums:
                try:
                    opening_val = float(nums[0])
                except ValueError:
                    pass

    if opening_val is None and closing_text and closing_text != "-":
        try:
            opening_val = float(closing_text)
        except ValueError:
            pass

    return closing_text, opening_val


def _find_odds_cells(row) -> List:
    """Busca todas as células de odds dentro de uma linha da tabela."""
    odds_cells = row.find_all(
        lambda tag: tag.name in ("a", "button", "div", "span") and (
            (tag.get("class") and any(
                x in " ".join(tag.get("class")).lower() 
                for x in ("oddscell__odd", "wcl-oddscell", "wcloddscell", "oddscell")
            ))
            or (tag.get("data-testid") and "oddscell" in tag.get("data-testid").lower())
        )
    )
    
    if odds_cells:
        primary_cells = []
        for cell in odds_cells:
            if not any(parent in odds_cells for parent in cell.parents):
                primary_cells.append(cell)
        return primary_cells

    # Fallback para tags <a> com odds numéricas
    return [
        a for a in row.find_all("a")
        if a.get_text(strip=True) and (a.get_text(strip=True) == "-" or re.search(r'\d+\.\d+|\d+', a.get_text(strip=True)))
    ]


def _find_odds_rows(soup: BeautifulSoup) -> List:
    """Localiza todas as linhas de bookmaker na tabela de odds, ignorando o cabeçalho."""
    all_rows = soup.find_all(
        lambda tag: tag.name in ("div", "tr") and (
            (tag.get("class") and any(
                x in " ".join(tag.get("class")).lower() 
                for x in ("wcloddsrow", "ui-table__row", "ui-tablerow", "wcl-tablerow", "wcl-oddsrow", "oddsrow", "tablerow")
            ))
            or
            (tag.get("data-testid") and any(
                x in tag.get("data-testid").lower() 
                for x in ("tablerow", "oddsrow", "wcl-tablerow", "wcl-oddsrow")
            ))
        )
    )

    odds_rows = []
    for r in all_rows:
        # Se for linha de cabeçalho ("1", "X", "2"), ignora
        if r.find(class_=lambda c: c and "wcloddsheader" in c.lower()) or r.find(lambda t: t.get("data-testid") == "wcl-scores-overline-02"):
            continue
        odds_rows.append(r)

    if odds_rows:
        return odds_rows

    bm_elements = soup.find_all(
        lambda tag: (
            tag.get("data-analytics-bookmaker-id")
            or tag.get("data-analytics-aff-id")
            or (tag.name == "a" and tag.get("href") and "/bookmaker/" in tag.get("href").lower())
            or (tag.get("class") and any("bookmaker" in c.lower() for c in (tag.get("class") or [])))
        )
    )

    candidate_rows = []
    for bm in bm_elements:
        parent = bm.parent
        while parent and parent.name != "body":
            p_class = " ".join(parent.get("class") or []).lower()
            p_testid = (parent.get("data-testid") or "").lower()
            
            has_odds = parent.find_all(
                lambda t: (t.get("data-testid") and "wcl-oddscell" in t.get("data-testid").lower())
                or (t.get("class") and any("oddscell" in c.lower() for c in (t.get("class") or [])))
            )
            
            if "wcloddsrow" in p_class or "row" in p_class or "row" in p_testid or "table" in p_class or has_odds:
                if parent not in candidate_rows:
                    candidate_rows.append(parent)
                break
            parent = parent.parent

    return candidate_rows


class FlashscoreParser:
    """Parser para conteúdo HTML da página do Flashscore."""
    
    @staticmethod
    def parse_odds_table(html: str, market_config: dict, bm_map: dict = None) -> tuple[List[Dict], Dict]:
        """Extrai as odds de uma aba de comparação de odds."""
        soup = BeautifulSoup(html, "html.parser")
        
        parsing_stats = {
            "unidentified_rows": 0,
            "unknown_bookmakers": set()
        }
        
        rows = _find_odds_rows(soup)
        
        if not rows:
            logger.debug(f"No odds rows found in HTML ({len(html)} bytes). Odds table may not have rendered.")
        
        results = []
        sys_market = market_config["sys_market"]
        period = market_config["period"]
        
        _unknown_bookmakers_in_batch = parsing_stats["unknown_bookmakers"]
        
        for index, row in enumerate(rows):
            if index == 0:
                logger.debug(f"FIRST ODDS ROW DOM:\n{row.prettify()}")
            
            raw_name = _extract_bookmaker_from_row(row)
            if raw_name is None:
                _log_unidentified_row(row)
                parsing_stats["unidentified_rows"] += 1
                continue
                
            our_bm_key = resolve_bookmaker(raw_name)
            if our_bm_key is None:
                if raw_name.lower() not in _unknown_bookmakers_in_batch:
                    _unknown_bookmakers_in_batch.add(raw_name.lower())
                    logger.warning(f"Bookmaker sem de-para prévio: '{raw_name}', usando slug '{raw_name.strip().lower().replace(' ', '_').replace('.', '')}'")
                our_bm_key = raw_name.strip().lower().replace(" ", "_").replace(".", "")
                
            cells = _find_odds_cells(row)
            vals = []
            opening_vals = []
            for cell in cells:
                closing_text, opening_val = _extract_cell_odds(cell)
                vals.append(closing_text)
                opening_vals.append(opening_val)
            
            parsed_vals = [float(v) if v and v != "-" else None for v in vals]
            parsed_vals = [v for v in parsed_vals if v is not None]
            if not parsed_vals:
                continue
                
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
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": opening_vals[1] if len(opening_vals) > 1 else None,
                            "opening_2": opening_vals[2] if len(opening_vals) > 2 else None,
                        })
                elif sys_market == "ou":
                    line_val = _extract_line_from_cell(row, signed=False)
                    if len(parsed_vals) >= 2 and line_val is not None:
                        real_odds = [v for v in parsed_vals if v != line_val]
                        if len(real_odds) < 2:
                            real_odds = parsed_vals[-2:]
                        if len(real_odds) >= 2:
                            results.append({
                                "bookmaker": our_bm_key,
                                "market_type": "ou",
                                "period": period,
                                "line": line_val,
                                "odds_1": real_odds[0],
                                "odds_x": None,
                                "odds_2": real_odds[1],
                                "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                                "opening_x": None,
                                "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
                            })
                elif sys_market == "ah":
                    line_val = _extract_line_from_cell(row, signed=True)
                    if line_val is None and len(parsed_vals) >= 2:
                        has_handicap_cell = row.find(
                            lambda tag: tag.get("class")
                            and any("handicap" in c.lower() for c in (tag.get("class") or []))
                        )
                        if not has_handicap_cell:
                            line_val = 0.0
                    
                    if line_val is not None and len(parsed_vals) >= 2:
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
                    if len(parsed_vals) >= 3:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "dc",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0],
                            "odds_x": parsed_vals[1],
                            "odds_2": parsed_vals[2],
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": opening_vals[1] if len(opening_vals) > 1 else None,
                            "opening_2": opening_vals[2] if len(opening_vals) > 2 else None,
                        })
                elif sys_market == "dnb":
                    if len(parsed_vals) >= 2:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "dnb",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0],
                            "odds_x": None,
                            "odds_2": parsed_vals[1],
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": None,
                            "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
                        })
                elif sys_market == "btts":
                    if len(parsed_vals) >= 2:
                        results.append({
                            "bookmaker": our_bm_key,
                            "market_type": "btts",
                            "period": period,
                            "line": None,
                            "odds_1": parsed_vals[0],
                            "odds_x": None,
                            "odds_2": parsed_vals[1],
                            "opening_1": opening_vals[0] if len(opening_vals) > 0 else None,
                            "opening_x": None,
                            "opening_2": opening_vals[1] if len(opening_vals) > 1 else None,
                        })
            except Exception as e:
                logger.debug(f"[FlashscoreParser] Ignorando row {raw_name} mal formatada: {e}")
                continue
                
        return results, parsing_stats

    @staticmethod
    def extract_match_ids_from_schedule(html: str) -> List[str]:
        """No DOM da página de schedule/results de uma liga, extrai os IDs dos matches."""
        ids = list(set(re.findall(r'g_1_([A-Za-z0-9]{8})', html) + re.findall(r'/match/([A-Za-z0-9]{8})', html)))
        return [i for i in ids if len(i) == 8 and i.isalnum() and i != "football"]
