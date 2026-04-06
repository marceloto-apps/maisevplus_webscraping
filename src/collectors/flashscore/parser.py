import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from src.db.logger import get_logger

logger = get_logger(__name__)

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
                continue
                
            # 2. Extrai os valores numéricos da linha
            # Procuramos por spans com valores de odds ou textos diretos nos links
            cells = row.find_all("a", class_=lambda c: c and ("odd" in c.lower() or "cell" in c.lower()))
            
            # Se não achou 'a' tags de cell, tenta pegar os spans (às vezes muda)
            if not cells:
                spans = row.find_all("span")
                # Filtra apenas os spans que parecem ser odds (números do tipo 1.95)
                vals = [s.get_text(strip=True) for s in spans if re.match(r'^\d+\.\d{2}$', s.get_text(strip=True))]
            else:
                # Extrai apenas os números internos ignorando setas de subida/descida (arrows)
                vals = []
                for cell in cells:
                    inner_span = cell.find("span")
                    val_text = inner_span.get_text(strip=True) if inner_span else cell.get_text(strip=True)
                    if re.match(r'^\d+\.\d{2}$', val_text) or val_text == "-":
                        vals.append(val_text)
            
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
                    # OU geralmente tem a linha na primeira célula após o nome do bookmaker (ex: 2.5) 
                    # Mas se a aba já é de uma linha específica, a linha pode estar no cabeçalho ou vir junta.
                    # Flashscore tipicamente exibe: Bookmaker | Total | Over | Under
                    # Assumimos que a tabela mostra a linha.
                    
                    # Para Extrair a linha (Total), achamos um elemento de texto visível que se parece com linha.
                    # Ele costuma estar solto na row ou num span específico.
                    line_text = row.get_text(separator=' ', strip=True)
                    line_match = re.search(r'\b(\d+\.5|\d+\.25|\d+\.75|\d+\.0)\b', line_text)
                    line_val = float(line_match.group(1)) if line_match else None
                    
                    if len(parsed_vals) >= 2 and line_val is not None:
                        # Frequentemente, a própria linha parseou no parsed_vals. 
                        # Precisamos excluir a linha se ela foi detectada como odd acidentalmente.
                        # Exemplo: parsed_vals = [2.50, 1.80, 2.05]
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
                    line_text = row.get_text(separator=' ', strip=True)
                    # Linhas AH podem ter sinais + ou -
                    line_match = re.search(r'([+-]?\d+\.5|[+-]?\d+\.25|[+-]?\d+\.75|[+-]?\d+\.0)\b', line_text)
                    
                    # As odds geralmente são as últimas duas colunas da row
                    if line_match and len(parsed_vals) >= 2:
                        line_val = float(line_match.group(1))
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
