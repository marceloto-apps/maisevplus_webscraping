"""
scripts/apply_migration_and_setup.py

Script para aplicar a migration 020 e cadastrar a liga/temporada da Argentina.
Desenvolvido para ambientes sem psql/pg_dump instalados.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

load_dotenv()


async def run_setup():
    print("=" * 80)
    print("  MIGRATION & SETUP HARNESS (ARGENTINA LIGA PROFESIONAL)")
    print("=" * 80)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 0. Limpeza de objetos criados acidentalmente no schema features no run anterior
        print("\n🧹 [0/4] Limpando criações acidentais no schema features...")
        try:
            await conn.execute("DROP VIEW IF EXISTS features.v_match_full CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS features.match_stats_fs CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS features.backup_match_stats_pre_020 CASCADE;")
            print("   ✅ Limpeza do schema features concluída.")
        except Exception as e:
            print(f"   ⚠️ Aviso durante a limpeza de features (pode ser ignorado): {e}")

        # 0.2. Limpeza de dados incorretos inseridos no schema public no run anterior
        print("\n🧹 [0.2/4] Limpando dados incorretos no schema public...")
        try:
            # Deleta partidas inseridas com ids incorretos (32 ou 136) no public.matches
            await conn.execute("DELETE FROM public.matches WHERE league_id = 32 OR season_id = 136;")
            # Deleta season incorreta
            await conn.execute("DELETE FROM public.seasons WHERE season_id = 136;")
            # Deleta liga incorreta
            await conn.execute("DELETE FROM public.leagues WHERE code = 'ARG_LP';")
            print("   ✅ Limpeza de dados incorretos no schema public concluída.")
        except Exception as e:
            print(f"   ⚠️ Aviso durante a limpeza do schema public (pode ser ignorado): {e}")

        # 0.5. Corrigir constraints do public.matches para apontar para o schema features
        print("\n🔧 [0.5/4] Apontando constraints de public.matches para o schema features...")
        try:
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_season_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_league_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_home_team_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_away_team_id_fkey;")

            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_season_id_fkey FOREIGN KEY (season_id) REFERENCES features.seasons(season_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_league_id_fkey FOREIGN KEY (league_id) REFERENCES features.leagues(league_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES features.teams(team_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES features.teams(team_id);")
            print("   ✅ Constraints de public.matches corrigidas com sucesso.")
        except Exception as e:
            print(f"   ❌ Erro ao corrigir constraints de public.matches: {e}")
            return

        # 1. Backup da tabela match_stats dentro do próprio banco
        print("\n📦 [1/4] Criando backup interno da tabela match_stats...")
        try:
            await conn.execute("CREATE TABLE IF NOT EXISTS backup_match_stats_pre_020 AS SELECT * FROM match_stats;")
            print("   ✅ Backup criado com sucesso: tabela 'backup_match_stats_pre_020'")
        except Exception as e:
            print(f"   ❌ Erro ao criar backup: {e}")
            return

        # 2. Ler e aplicar a migration 020
        print("\n🚀 [2/4] Aplicando a migration 020_flashscore_extended.sql...")
        migration_path = os.path.join(os.getcwd(), "migrations", "020_flashscore_extended.sql")
        if not os.path.exists(migration_path):
            print(f"   ❌ Arquivo de migração não encontrado em {migration_path}")
            return

        with open(migration_path, "r", encoding="utf-8") as f:
            migration_sql = f.read()

        try:
            # Executa todo o script SQL
            await conn.execute(migration_sql)
            print("   ✅ Migration 020 aplicada com sucesso!")
        except Exception as e:
            print(f"   ❌ Erro ao aplicar migration: {e}")
            return

        # Garantir que o search_path volte para "features, public" após a migration (que roda com "public" interno)
        await conn.execute("SET search_path TO features, public;")

        # 2b. Corrigir sequências de ID desalinhadas no banco de dados (evitar duplicate key violations)
        print("\n⚙️ [2.5/4] Corrigindo desalinhamento de sequências no banco de dados...")
        try:
            await conn.execute("SELECT setval('teams_team_id_seq', COALESCE((SELECT MAX(team_id) FROM teams), 1));")
            await conn.execute("SELECT setval('leagues_league_id_seq', COALESCE((SELECT MAX(league_id) FROM leagues), 1));")
            await conn.execute("SELECT setval('seasons_season_id_seq', COALESCE((SELECT MAX(season_id) FROM seasons), 1));")
            await conn.execute("SELECT setval('team_aliases_alias_id_seq', COALESCE((SELECT MAX(alias_id) FROM team_aliases), 1));")
            print("   ✅ Sequências de ID alinhadas com sucesso.")
        except Exception as e:
            print(f"   ⚠️ Aviso ao alinhar sequências: {e}")

        # 3. Inserir a Liga Argentina
        print("\n🏆 [3/4] Cadastrando a liga 'ARG_LP' (Liga Profesional Argentina)...")
        insert_league_sql = """
            INSERT INTO leagues (
                code, 
                name, 
                country, 
                flashscore_path, 
                primary_source,
                season_format,
                tier,
                is_active
            )
            VALUES (
                'ARG_LP', 
                'Liga Profesional', 
                'Argentina', 
                'football/argentina/liga-profesional', 
                'flashscore',
                'feb_dec',
                1,
                TRUE
            )
            ON CONFLICT (code) DO UPDATE SET
                flashscore_path = EXCLUDED.flashscore_path,
                primary_source = EXCLUDED.primary_source
            RETURNING league_id;
        """
        try:
            league_id = await conn.fetchval(insert_league_sql)
            print(f"   ✅ Liga cadastrada/atualizada com sucesso! ID: {league_id}")
        except Exception as e:
            print(f"   ❌ Erro ao cadastrar liga: {e}")
            return

        # 4. Inserir a Temporada 2026 para a liga
        print("\n📅 [4/4] Cadastrando a temporada '2026'...")
        insert_season_sql = """
            INSERT INTO seasons (
                league_id,
                label,
                start_date,
                end_date,
                footystats_season_id,
                is_current
            )
            VALUES (
                $1,
                '2026',
                '2026-02-01',
                '2026-12-31',
                0,
                TRUE
            )
            ON CONFLICT (league_id, label) DO UPDATE SET
                is_current = EXCLUDED.is_current
            RETURNING season_id;
        """
        try:
            season_id = await conn.fetchval(insert_season_sql, league_id)
            print(f"   ✅ Temporada cadastrada/atualizada com sucesso! ID: {season_id}")
        except Exception as e:
            print(f"   ❌ Erro ao cadastrar temporada: {e}")
            return

    await pool.close()
    print("\n" + "=" * 80)
    print("  SETUP E MIGRAÇÃO CONCLUÍDOS COM SUCESSO!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_setup())
