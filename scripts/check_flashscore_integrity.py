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
    
    try:
        async with AsyncCamoufox(headless=True, os="linux") as browser:
            context = await browser.new_context(
                timezone_id="America/Sao_Paulo",
                locale="pt-BR"
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            try:
                await page.wait_for_selector('div[id^="g_1_"]', timeout=15000)
            except Exception:
                pass
                
            await page.wait_for_timeout(2000)
            html = await page.content()
            await page.close()
            await context.close()
            
        soup = BeautifulSoup(html, "html.parser")
        match_div = soup.find("div", id=re.compile(r'^g_1_'))
        
        if not match_div:
            failed_field = "match_node (div g_1_)"
            error_reason = "Nenhum div g_1_ (nó de partida) foi encontrado na página."
            # Pega uma parte do body para analisar
            body = soup.find("body")
            match_html_sample = str(body)[:1000] if body else html[:1000]
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
            else:
                home_team = home_node.get_text(strip=True)
                away_team = away_node.get_text(strip=True)
                date_text = time_node.get_text(strip=True)
                
                if not home_team or not away_team or not date_text:
                    failed_field = "text_extraction (conteúdo de texto)"
                    error_reason = f"Extração de texto retornou campos vazios: Home='{home_team}', Away='{away_team}', Data='{date_text}'"
                else:
                    logger.info(f"Integridade OK! Exemplo: {home_team} vs {away_team} em {date_text} (ID: {fs_id})")
                    success = True
                    
    except Exception as e:
        error_reason = f"Erro de execução do Camoufox / Exception: {str(e)}"
        failed_field = "execution"
        match_html_sample = "N/A - Erro de Execução"
        
    if not success:
        logger.error(f"Integridade falhou! Campo: {failed_field}. Motivo: {error_reason}")
        
        # Escapar caracteres do HTML para o Telegram
        escaped_html = match_html_sample.replace("<", "&lt;").replace(">", "&gt;")
        
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
            f"para extrair esse campo em src/collectors/flashscore/discovery.py.\n"
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
