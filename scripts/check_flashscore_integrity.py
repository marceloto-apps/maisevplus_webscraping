"""
scripts/check_flashscore_integrity.py

Script diário de integridade do Flashscore.
Valida se as classes HTML principais de listagem permanecem válidas.
Caso detecte mudança, envia um alerta com um prompt pronto para correção via IA.

Uso:
    xvfb-run -a python scripts/check_flashscore_integrity.py
"""
import asyncio
import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert
from camoufox.async_api import AsyncCamoufox
from bs4 import BeautifulSoup

logger = get_logger(__name__)

async def main():
    load_dotenv()
    await TelegramAlert.init()
    
    url = "https://www.flashscore.com/football/england/premier-league/fixtures/"
    logger.info(f"Iniciando verificação de integridade do Flashscore usando: {url}")
    
    success = False
    error_reason = ""
    failed_field = ""
    match_html_sample = ""
    
    odds_html_sample = ""
    try:
        async with AsyncCamoufox(headless=True, os="linux") as browser:
            context = await browser.new_context(
                timezone_id="America/Sao_Paulo",
                locale="pt-BR"
            )
            page = await context.new_page()
            
            # 1. Carrega a listagem de fixtures (ou resultados se fixtures não tiver odds disponíveis)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('div[id^="g_1_"], a[id^="match-row-g_1_"]', timeout=20000)
            except Exception:
                pass
                
            await page.wait_for_timeout(2000)
            html = await page.content()
            
            # 2. Procura por partidas e tenta encontrar uma com aba de odds disponível
            soup = BeautifulSoup(html, "html.parser")
            match_divs = soup.find_all("div", id=re.compile(r'^g_1_'))
            
            # Se a página de fixtures não tiver partidas, tenta a página de resultados
            if not match_divs:
                url_results = "https://www.flashscore.com/football/england/premier-league/results/"
                logger.info(f"Nenhum jogo em fixtures, tentando resultados: {url_results}")
                await page.goto(url_results, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector('div[id^="g_1_"]', timeout=20000)
                except Exception:
                    pass
                await page.wait_for_timeout(2000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                match_divs = soup.find_all("div", id=re.compile(r'^g_1_'))

            # Tenta encontrar uma partida que tenha odds disponíveis (máximo 2 tentativas em fixtures)
            selected_div = None
            for m_div in match_divs[:2]:
                test_fs_id = m_div.get("id", "")[4:]
                if not test_fs_id:
                    continue
                    
                base_match_url = f"https://www.flashscore.com/match/{test_fs_id}/"
                logger.info(f"Testando partida para odds em fixtures: {base_match_url}")
                try:
                    await page.goto(base_match_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    # Tenta fechar cookie banner se existir
                    try:
                        accept_btn = page.locator('button#onetrust-accept-btn-handler')
                        if await accept_btn.count() > 0:
                            await accept_btn.click(timeout=2000)
                            await page.wait_for_timeout(500)
                    except Exception:
                        pass
                        
                    # Clica na aba de odds (se houver) ou tenta a URL direta de odds
                    odds_tab = await page.query_selector("a[href*='/odds/']")
                    target_odds_url = None
                    if odds_tab:
                        target_odds_url = await odds_tab.get_attribute("href")
                        if target_odds_url and target_odds_url.startswith("/"):
                            target_odds_url = f"https://www.flashscore.com{target_odds_url}"
                    else:
                        canonical = page.url.split("?")[0].rstrip("/")
                        target_odds_url = f"{canonical}/odds/1x2-odds/full-time/?mid={test_fs_id}"

                    if target_odds_url:
                        await page.goto(target_odds_url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        rendered_html = await page.content()
                        # Verifica se não é empty state
                        if "wcl-emptyState" not in rendered_html and ("ui-table__row" in rendered_html or "oddsCell" in rendered_html):
                            odds_html_sample = rendered_html
                            selected_div = m_div
                            logger.info(f"Partida com odds validada com sucesso: {test_fs_id}")
                            break
                except Exception as e:
                    logger.warning(f"Erro ao testar odds para {test_fs_id}: {e}")

            # Se fixtures não renderizou odds para nenhuma partida, tenta resultados recentes de liga ativa (ex: Brasileirão Série A ou arquivo)
            if not odds_html_sample:
                logger.info("Nenhuma partida com odds em fixtures da Premier League. Tentando resultados recentes de liga ativa...")
                fallback_urls = [
                    "https://www.flashscore.com/football/brazil/serie-a/results/",
                    "https://www.flashscore.com/football/england/premier-league-2024-2025/results/"
                ]
                for url_res in fallback_urls:
                    try:
                        logger.info(f"Navegando para: {url_res}")
                        await page.goto(url_res, wait_until="domcontentloaded", timeout=30000)
                        try:
                            await page.wait_for_selector('div[id^="g_1_"]', timeout=15000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(2000)
                        res_html = await page.content()
                        res_soup = BeautifulSoup(res_html, "html.parser")
                        res_divs = res_soup.find_all("div", id=re.compile(r'^g_1_'))
                        
                        for m_div in res_divs[:5]:
                            test_fs_id = m_div.get("id", "")[4:]
                            if not test_fs_id:
                                continue
                            base_match_url = f"https://www.flashscore.com/match/{test_fs_id}/"
                            logger.info(f"Testando partida para odds em resultados: {base_match_url}")
                            await page.goto(base_match_url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(2000)
                            
                            odds_tab = await page.query_selector("a[href*='/odds/']")
                            target_odds_url = None
                            if odds_tab:
                                target_odds_url = await odds_tab.get_attribute("href")
                                if target_odds_url and target_odds_url.startswith("/"):
                                    target_odds_url = f"https://www.flashscore.com{target_odds_url}"
                            else:
                                canonical = page.url.split("?")[0].rstrip("/")
                                target_odds_url = f"{canonical}/odds/1x2-odds/full-time/?mid={test_fs_id}"

                            if target_odds_url:
                                await page.goto(target_odds_url, wait_until="domcontentloaded", timeout=30000)
                                await page.wait_for_timeout(3000)
                                rendered_html = await page.content()
                                if "wcl-emptyState" not in rendered_html and ("ui-table__row" in rendered_html or "oddsCell" in rendered_html):
                                    odds_html_sample = rendered_html
                                    selected_div = m_div
                                    logger.info(f"Partida de resultados com odds validada: {test_fs_id}")
                                    break
                        if odds_html_sample:
                            break
                    except Exception as e:
                        logger.warning(f"Erro ao buscar odds na página de resultados {url_res}: {e}")
                    
            await page.close()
            await context.close()
            
        soup = BeautifulSoup(html, "html.parser")
        match_div = selected_div or soup.find("div", id=re.compile(r'^g_1_'))
        
        if not match_div:
            failed_field = "match_node (div g_1_)"
            error_reason = "Nenhum div g_1_ (nó de partida) foi encontrado na página."
            body = soup.find("body")
            match_html_sample = str(body)[:1000] if body else html[:1000]
            # Adiciona contexto extra: tamanho do HTML e URL final (para detectar anti-bot/redirecionamentos)
            error_reason += f" | HTML size: {len(html)} bytes | URL final: {page.url if 'page' in dir() else url}"
        else:
            match_html_sample = str(match_div)[:1200]
            fs_id = match_div.get("id", "")[4:]
            
            home_node = match_div.find(class_=re.compile("homeParticipant"))
            away_node = match_div.find(class_=re.compile("awayParticipant"))
            time_node = match_div.find(class_=re.compile("event__(stageTime|time)"))
            
            if not fs_id:
                failed_field = "flashscore_id"
                error_reason = "ID da partida não pôde ser extraído do atributo 'id' do div."
            elif not home_node:
                failed_field = "homeParticipant (time da casa)"
                error_reason = "Nó de classe 'homeParticipant' não encontrado dentro do nó da partida."
            elif not away_node:
                failed_field = "awayParticipant (time visitante)"
                error_reason = "Nó de classe 'awayParticipant' não encontrado dentro do nó da partida."
            elif not time_node:
                failed_field = "event__time / event__stageTime (horário do jogo)"
                error_reason = "Nó de classe 'event__stageTime' ou 'event__time' não encontrado dentro do nó da partida."
            elif not odds_html_sample:
                failed_field = "oddsCell__odd (tabela de odds)"
                error_reason = "Página de comparação de odds não renderizou nenhuma linha/célula de odds."
                match_html_sample = html[:1000]
            else:
                home_team = home_node.get_text(strip=True)
                away_team = away_node.get_text(strip=True)
                date_text = time_node.get_text(strip=True)
                
                # Validação do seletor da opening odd no HTML da página de odds
                odds_soup = BeautifulSoup(odds_html_sample, "html.parser")
                odd_cells = odds_soup.find_all(
                    lambda tag: tag.name in ("a", "div", "span", "td") and (
                        (tag.get("data-testid") and "wcl-oddscell" in tag.get("data-testid").lower())
                        or
                        (tag.get("class") and any(x in " ".join(tag.get("class")).lower() for x in ("oddscell__odd", "oddscellodd", "wcl-oddscell", "wcl-oddsvalue", "oddscell")))
                    )
                )
                
                # Filtrar elementos de bookmakers ou células de handicap
                odd_cells = [
                    c for c in odd_cells
                    if not ("/bookmaker/" in (c.get("href") or "").lower() or "bookmaker" in " ".join(c.get("class") or []).lower())
                    and not ("handicap" in " ".join(c.get("class") or []).lower() or "handicap" in (c.get("data-testid") or "").lower())
                ]
                
                # Verifica se encontrou células de odds
                if not odd_cells:
                    failed_field = "oddsCell__odd (células de odds)"
                    error_reason = "Nenhuma célula de odd foi encontrada no HTML da página de comparação de odds."
                    match_html_sample = odds_html_sample[:1200]
                else:
                    # Verifica se pelo menos uma célula tem o separador '»' no title (na própria célula ou em elementos filhos)
                    has_opening = False
                    for cell in odd_cells:
                        for target in [cell] + list(cell.find_all(True)):
                            t = target.get('title') or target.get('data-title') or target.get('data-tooltip') or ''
                            if '»' in t:
                                has_opening = True
                                break
                        if has_opening:
                            break

                    if not has_opening:
                        failed_field = "oddsCell__odd[title*='»'] (opening odds)"
                        error_reason = "Nenhuma célula de odd possui o atributo 'title' contendo o separador '»' de opening odds."
                        match_html_sample = str(odd_cells[0])[:1200]
                    elif not home_team or not away_team or not date_text:
                        failed_field = "text_extraction (conteúdo de texto)"
                        error_reason = f"Extração de texto retornou campos vazios: Home='{home_team}', Away='{away_team}', Data='{date_text}'"
                    else:
                        logger.info(f"Integridade OK! Exemplo: {home_team} vs {away_team} em {date_text} (ID: {fs_id}) | Opening odds validadas!")
                        success = True
                        
    except Exception as e:
        error_reason = f"Erro de execução do Camoufox / Exception: {str(e)}"
        failed_field = "execution"
        match_html_sample = "N/A - Erro de Execução"
        
    if not success:
        logger.error(f"Integridade falhou! Campo: {failed_field}. Motivo: {error_reason}")
        
        # Escapar caracteres do HTML para o Telegram
        escaped_html = match_html_sample.replace("<", "&lt;").replace(">", "&gt;")
        
        target_file_hint = "src/collectors/flashscore/parser.py" if "odds" in failed_field.lower() else "src/collectors/flashscore/discovery.py"
        
        # Constrói a mensagem e o prompt de auto-correção
        msg = (
            f"🚨 *CRITICAL: Flashscore Layout Quebrado!*\n\n"
            f"O script de monitoramento detectou uma falha de parsing.\n"
            f"• *Campo que falhou:* `{failed_field}`\n"
            f"• *Motivo:* {error_reason}\n\n"
            f"*Copie o prompt de correção abaixo e cole na IA:*\n"
            f"```\n"
            f"A estrutura do HTML do Flashscore mudou e o nosso script de importação quebrou.\n"
            f"Falha ao extrair o campo: {failed_field}\n\n"
            f"Aqui está um trecho de exemplo do HTML do nó de partida:\n"
            f"{match_html_sample}\n\n"
            f"Por favor, analise a estrutura e me forneça o código BeautifulSoup corrigido "
            f"para extrair esse campo em {target_file_hint}.\n"
            f"```"
        )
        
        # Envia como alerta crítico no Telegram
        TelegramAlert.fire("critical", msg)
    else:
        logger.info("Flashscore integrity check completed successfully.")
        
    await asyncio.sleep(1)
    await TelegramAlert.close()

if __name__ == "__main__":
    asyncio.run(main())
