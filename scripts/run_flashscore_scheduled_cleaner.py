"""
scripts/run_flashscore_scheduled_cleaner.py

Rotina diária para limpar partidas que ficaram presas no status 'scheduled'
após o kickoff. Acessa as páginas de detalhes e atualiza os status e placares.

Uso:
    xvfb-run -a python scripts/run_flashscore_scheduled_cleaner.py
"""
import asyncio
import os
import sys
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

# Garantir que o diretório raiz esteja no path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAMOUFOX_DATA_DIR"] = os.path.join(os.getcwd(), ".camoufox_profile")

from src.db.pool import get_pool
from src.db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert
from camoufox.async_api import AsyncCamoufox

logger = get_logger(__name__)

async def clean_match(conn, page, match_id_uuid, fs_id, home_team, away_team, kickoff):
    base_url = f"https://www.flashscore.com/match/{fs_id}/"
    logger.info(f"Processando partida: {home_team} vs {away_team} | FS_ID: {fs_id} | Kickoff: {kickoff}")
    
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        logger.warning(f"Timeout/Erro ao carregar {fs_id}: {e}")
        return False

    # Aceitar banner de cookies se estiver presente
    try:
        accept_btn = page.locator('button#onetrust-accept-btn-handler')
        await accept_btn.wait_for(state="visible", timeout=3000)
        await accept_btn.click()
        await page.wait_for_timeout(500)
    except Exception:
        pass

    # Aguardar o wrapper do placar ou status
    try:
        await page.wait_for_selector('div.detailScore__wrapper, span.fixedHeader__status', timeout=5000)
    except Exception:
        pass

    ft_home = ft_away = ht_home = ht_away = None
    match_status = None

    # 1. Tenta extrair placares FT
    score_wrapper = page.locator("div.detailScore__wrapper")
    if await score_wrapper.count() > 0:
        span_elements = score_wrapper.locator("span")
        if await span_elements.count() >= 3:
            ft_home_text = await span_elements.nth(0).inner_text()
            ft_away_text = await span_elements.nth(2).inner_text()
            if ft_home_text.strip().isdigit() and ft_away_text.strip().isdigit():
                ft_home = int(ft_home_text.strip())
                ft_away = int(ft_away_text.strip())
                match_status = "finished"

    # 2. Se não extraiu FT, vamos tentar checar status alternativo no cabeçalho
    # ex: Adiado (Postponed), Cancelado (Cancelled), etc.
    status_locator = page.locator("div.detailScore__status, span.fixedHeader__status, div.fixedHeader__status")
    status_text = ""
    if await status_locator.count() > 0:
        status_text = (await status_locator.first.inner_text()).lower()
        logger.debug(f"Status extraído do Flashscore para {fs_id}: {status_text}")
        
        postponed_keywords = ["postp", "adiad", "atr", "delay", "postponed"]
        cancelled_keywords = ["canc", "cancel", "wo", "w.o"]
        
        if any(k in status_text for k in postponed_keywords):
            match_status = "postponed"
        elif any(k in status_text for k in cancelled_keywords):
            match_status = "cancelled"

    # 3. Extrai placar HT (caso tenha finalizado)
    if match_status == "finished":
        summary_headers = page.locator("div.wclHeaderSection--summary")
        header_count = await summary_headers.count()
        for i in range(header_count):
            header = summary_headers.nth(i)
            spans = header.locator("span")
            if await spans.count() >= 2:
                label = await spans.nth(0).inner_text()
                score_val = await spans.nth(1).inner_text()
                first_half_keywords = ["1st half", "1o tempo", "1º tempo", "1st_half", "1. halbzeit", "1er temps", "1. tempo", "1 tempo", "1st"]
                if any(k in label.lower() for k in first_half_keywords):
                    parts = score_val.split("-")
                    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                        ht_home = int(parts[0].strip())
                        ht_away = int(parts[1].strip())
                        break
                    parts_colon = score_val.split(":")
                    if len(parts_colon) == 2 and parts_colon[0].strip().isdigit() and parts_colon[1].strip().isdigit():
                        ht_home = int(parts_colon[0].strip())
                        ht_away = int(parts_colon[1].strip())
                        break

    # 3.5. Extrai e valida a data de kickoff do Flashscore
    start_time_locator = page.locator(".duelParticipant__startTime")
    page_kickoff_dt = None
    if await start_time_locator.count() > 0:
        time_text = await start_time_locator.first.inner_text()
        time_text = time_text.strip()
        # Expressão para DD.MM.YYYY HH:MM ou DD.MM. HH:MM
        m = re.search(r'(\d{2})\.(\d{2})\.(?:\s*(\d{4}))?\s+(\d{2}):(\d{2})', time_text)
        if m:
            day = int(m.group(1))
            month = int(m.group(2))
            year_str = m.group(3)
            hour = int(m.group(4))
            minute = int(m.group(5))
            
            # Se não tiver ano explícito, assume o ano do kickoff atual no banco
            if year_str:
                year = int(year_str)
            else:
                year = kickoff.year
                
            from zoneinfo import ZoneInfo
            sp_tz = ZoneInfo("America/Sao_Paulo")
            page_kickoff_dt = datetime(year, month, day, hour, minute, tzinfo=sp_tz)

    kickoff_changed = False
    if page_kickoff_dt and abs((page_kickoff_dt - kickoff.astimezone(page_kickoff_dt.tzinfo)).total_seconds()) > 60:
        kickoff_changed = True
        logger.info(f"Partida {fs_id} teve kickoff alterado: DB={kickoff} -> Página={page_kickoff_dt}")

    # 4. Atualizar o DB conforme o resultado
    if match_status == "finished" and ft_home is not None and ft_away is not None:
        logger.info(f"Atualizando partida finalizada no DB: {home_team} {ft_home}-{ft_away} {away_team}")
        await conn.execute("""
            UPDATE matches
            SET status = 'finished',
                ft_home = $1, ft_away = $2,
                ht_home = $3, ht_away = $4,
                kickoff = CASE WHEN $5::boolean THEN $6::timestamptz ELSE kickoff END,
                scraping_flashscore = FALSE,
                updated_at = NOW()
            WHERE match_id = $7
        """, ft_home, ft_away, ht_home, ht_away, kickoff_changed, page_kickoff_dt, match_id_uuid)
        return "finished"
        
    elif match_status in ("postponed", "cancelled"):
        logger.info(f"Atualizando status da partida no DB para: {match_status}")
        await conn.execute("""
            UPDATE matches
            SET status = $1,
                kickoff = CASE WHEN $2::boolean THEN $3::timestamptz ELSE kickoff END,
                scraping_flashscore = FALSE,
                updated_at = NOW()
            WHERE match_id = $4
        """, match_status, kickoff_changed, page_kickoff_dt, match_id_uuid)
        return match_status
        
    elif kickoff_changed:
        logger.info(f"Atualizando apenas data de kickoff no DB para data futura: {page_kickoff_dt}")
        await conn.execute("""
            UPDATE matches
            SET kickoff = $1,
                status = 'scheduled',
                updated_at = NOW()
            WHERE match_id = $2
        """, page_kickoff_dt, match_id_uuid)
        return "rescheduled"

    else:
        logger.warning(f"Partida {fs_id} avaliada, mas nenhum status/placar conclusivo foi extraído (Status Text: '{status_text}')")
        return None

async def main():
    load_dotenv()
    await TelegramAlert.init()
    
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Busca todas as partidas presas no status scheduled no passado
        # Margem de segurança de 3 horas após o kickoff
        rows = await conn.fetch("""
            SELECT m.match_id, m.flashscore_id, m.kickoff,
                   th.name_canonical as home_team, ta.name_canonical as away_team
            FROM matches m
            JOIN teams th ON m.home_team_id = th.team_id
            JOIN teams ta ON m.away_team_id = ta.team_id
            WHERE m.status = 'scheduled'
              AND m.flashscore_id IS NOT NULL
              AND m.kickoff < NOW() - INTERVAL '3 hours'
            ORDER BY m.kickoff ASC
        """)
        
        if not rows:
            logger.info("Nenhuma partida presa encontrada para limpar.")
            msg = "🧹 *Flashscore Scheduled Cleaner*\n\nNenhuma partida travada encontrada no passado para limpar."
            TelegramAlert.fire("info", msg)
            await TelegramAlert.close()
            await pool.close()
            return
            
        logger.info(f"Encontradas {len(rows)} partidas travadas no passado. Iniciando Camoufox...")
        
        updated_counts = {"finished": 0, "postponed": 0, "cancelled": 0, "rescheduled": 0, "ignored": 0}
        
        async with AsyncCamoufox(headless=True, os="linux") as browser:
            context = await browser.new_context(
                timezone_id="America/Sao_Paulo",
                locale="pt-BR"
            )
            page = await context.new_page()
            
            for r in rows:
                try:
                    res = await clean_match(
                        conn, page, r["match_id"], r["flashscore_id"],
                        r["home_team"], r["away_team"], r["kickoff"]
                    )
                    if res in updated_counts:
                        updated_counts[res] += 1
                    else:
                        updated_counts["ignored"] += 1
                except Exception as e:
                    logger.error(f"Erro no processamento da partida {r['flashscore_id']}: {e}")
                    updated_counts["ignored"] += 1
                    
                await asyncio.sleep(2)
                
            await page.close()
            await context.close()
            
        total_updated = updated_counts["finished"] + updated_counts["postponed"] + updated_counts["cancelled"] + updated_counts["rescheduled"]
        msg = (
            f"🧹 *Flashscore Scheduled Cleaner*\n"
            f"Status: SUCCESS\n\n"
            f"Partidas avaliadas: {len(rows)}\n"
            f"• Atualizadas p/ Finalizadas: {updated_counts['finished']}\n"
            f"• Atualizadas p/ Adiadas: {updated_counts['postponed']}\n"
            f"• Atualizadas p/ Canceladas: {updated_counts['cancelled']}\n"
            f"• Reagendadas (novo kickoff): {updated_counts['rescheduled']}\n"
            f"• Ignoradas (inconclusivo): {updated_counts['ignored']}\n\n"
            f"Total de atualizações no DB: {total_updated}"
        )
        TelegramAlert.fire("info", msg)
        
    await pool.close()
    await asyncio.sleep(1)
    await TelegramAlert.close()

if __name__ == "__main__":
    asyncio.run(main())
