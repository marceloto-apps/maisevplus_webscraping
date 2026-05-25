"""
scripts/apply_migration_and_setup.py

Script para consolidar e migrar dados do schema 'features' para o 'public',
limpar tabelas duplicadas no schema 'features', corrigir chaves estrangeiras
no public.matches, aplicar a migração 020 e registrar/atualizar a liga da Argentina.
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
    print("  DATABASE CONSOLIDATION & SETUP HARNESS (PUBLIC SCHEMA)")
    print("=" * 80)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Enforcar search_path como public para as operações iniciais
        await conn.execute("SET search_path TO public;")

        # 0. Migrar os dados de features para o schema public (preservando IDs)
        print("\n📦 [0/5] Migrando dados de 'features' para o schema 'public'...")
        try:
            # 0.1. Ligas
            await conn.execute("""
                INSERT INTO public.leagues (
                    league_id, code, name, country, tier, season_format, 
                    football_data_code, football_data_type, understat_name, 
                    fbref_id, flashscore_path, footystats_name, 
                    api_football_league_id, xg_source, is_active, created_at, primary_source
                )
                SELECT 
                    league_id, code, name, country, tier, season_format, 
                    football_data_code, football_data_type, understat_name, 
                    fbref_id, flashscore_path, footystats_name, 
                    api_football_league_id, xg_source, is_active, created_at, primary_source
                FROM features.leagues
                WHERE league_id NOT IN (SELECT league_id FROM public.leagues)
                  AND code NOT IN (SELECT code FROM public.leagues);
            """)
            print("   ✅ Ligas migradas.")

            # 0.2. Times
            await conn.execute("""
                INSERT INTO public.teams (
                    team_id, name_canonical, country, api_football_id, created_at
                )
                SELECT 
                    team_id, name_canonical, country, api_football_id, created_at
                FROM features.teams
                WHERE team_id NOT IN (SELECT team_id FROM public.teams);
            """)
            print("   ✅ Times migrados.")

            # 0.3. Temporadas
            await conn.execute("""
                INSERT INTO public.seasons (
                    season_id, league_id, label, start_date, end_date, 
                    footystats_season_id, football_data_season, is_current
                )
                SELECT 
                    season_id, league_id, label, start_date, end_date, 
                    footystats_season_id, football_data_season, is_current
                FROM features.seasons
                WHERE season_id NOT IN (SELECT season_id FROM public.seasons);
            """)
            print("   ✅ Temporadas migradas.")

            # 0.4. Aliases de Times
            await conn.execute("""
                INSERT INTO public.team_aliases (
                    alias_id, team_id, source, alias_name
                )
                SELECT 
                    alias_id, team_id, source, alias_name
                FROM features.team_aliases
                WHERE alias_id NOT IN (SELECT alias_id FROM public.team_aliases)
                  AND (source, alias_name) NOT IN (SELECT source, alias_name FROM public.team_aliases);
            """)
            print("   ✅ Aliases de times migrados.")

            # 0.5. Aliases desconhecidos
            await conn.execute("""
                INSERT INTO public.unknown_aliases (
                    id, source, raw_name, league_code, first_seen, resolved, resolved_team_id, resolved_at
                )
                SELECT 
                    id, source, raw_name, league_code, first_seen, resolved, resolved_team_id, resolved_at
                FROM features.unknown_aliases
                WHERE id NOT IN (SELECT id FROM public.unknown_aliases)
                  AND (source, raw_name) NOT IN (SELECT source, raw_name FROM public.unknown_aliases);
            """)
            print("   ✅ Aliases desconhecidos migrados.")
            
        except Exception as e:
            print(f"   ⚠️ Aviso/Erro na migração de dados (pode ser ignorado se já migrado): {e}")

        # 1. Limpeza de dados incorretos inseridos no schema public
        print("\n🧹 [1/5] Limpando registros/IDs incorretos e duplicados no public...")
        try:
            # Deleta partidas inseridas com ids de liga/season incorretos (32 ou 136)
            await conn.execute("DELETE FROM public.matches WHERE league_id = 32 OR season_id = 136;")
            # Deleta a season incorreta do public
            await conn.execute("DELETE FROM public.seasons WHERE season_id = 136;")
            # Deleta a liga incorreta com ID 32 do public
            await conn.execute("DELETE FROM public.leagues WHERE code = 'ARG_LP' AND league_id = 32;")
            print("   ✅ Limpeza do schema public concluída.")
        except Exception as e:
            print(f"   ⚠️ Aviso durante a limpeza do schema public: {e}")

        # 2. Deletar as tabelas duplicadas no schema features (Ignorado por decisão de design)
        print("\n🗑️ [2/5] Ignorando a remoção de tabelas no schema 'features'...")

        # 3. Corrigir constraints do public.matches para apontar apenas para tabelas do public
        print("\n🔧 [3/5] Corrigindo chaves estrangeiras no public.matches...")
        try:
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_season_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_league_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_home_team_id_fkey;")
            await conn.execute("ALTER TABLE public.matches DROP CONSTRAINT IF EXISTS matches_away_team_id_fkey;")

            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_season_id_fkey FOREIGN KEY (season_id) REFERENCES public.seasons(season_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_league_id_fkey FOREIGN KEY (league_id) REFERENCES public.leagues(league_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES public.teams(team_id);")
            await conn.execute("ALTER TABLE public.matches ADD CONSTRAINT matches_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES public.teams(team_id);")
            print("   ✅ Chaves estrangeiras apontadas para o public schema com sucesso.")
        except Exception as e:
            print(f"   ❌ Erro crítico ao ajustar chaves estrangeiras: {e}")
            return

        # 4. Backup interno da tabela match_stats
        print("\n📦 [4/5] Criando backup interno da tabela match_stats...")
        try:
            await conn.execute("CREATE TABLE IF NOT EXISTS public.backup_match_stats_pre_020 AS SELECT * FROM public.match_stats;")
            print("   ✅ Backup criado: 'backup_match_stats_pre_020'")
        except Exception as e:
            print(f"   ❌ Erro ao criar backup: {e}")
            return

        # 5. Aplicar a migration 020 no public schema
        print("\n🚀 [5/5] Aplicando a migration 020_flashscore_extended.sql no schema public...")
        migration_path = os.path.join(os.getcwd(), "migrations", "020_flashscore_extended.sql")
        if not os.path.exists(migration_path):
            print(f"   ❌ Arquivo de migração não encontrado em {migration_path}")
            return

        with open(migration_path, "r", encoding="utf-8") as f:
            migration_sql = f.read()

        try:
            await conn.execute(migration_sql)
            print("   ✅ Migration 020 aplicada com sucesso!")
        except Exception as e:
            print(f"   ❌ Erro ao aplicar migration: {e}")
            return

        # Resetar sequências de IDs no public
        print("\n⚙️ Corrigindo desalinhamento de sequências no schema public...")
        try:
            await conn.execute("SELECT setval('public.teams_team_id_seq', COALESCE((SELECT MAX(team_id) FROM public.teams), 1));")
            await conn.execute("SELECT setval('public.leagues_league_id_seq', COALESCE((SELECT MAX(league_id) FROM public.leagues), 1));")
            await conn.execute("SELECT setval('public.seasons_season_id_seq', COALESCE((SELECT MAX(season_id) FROM public.seasons), 1));")
            await conn.execute("SELECT setval('public.team_aliases_alias_id_seq', COALESCE((SELECT MAX(alias_id) FROM public.team_aliases), 1));")
            print("   ✅ Sequências alinhadas.")
        except Exception as e:
            print(f"   ⚠️ Aviso ao alinhar sequências: {e}")

        # Registrar/atualizar a Liga Argentina no public schema
        print("\n🏆 Cadastrando/Atualizando a liga 'ARG_LP' no public...")
        insert_league_sql = """
            INSERT INTO public.leagues (
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
            print(f"   ✅ Liga 'ARG_LP' cadastrada/atualizada. ID: {league_id}")
        except Exception as e:
            print(f"   ❌ Erro ao cadastrar liga: {e}")
            return

        # Registrar/atualizar Temporada 2026 no public schema
        print("\n📅 Cadastrando/Atualizando a temporada '2026' no public...")
        insert_season_sql = """
            INSERT INTO public.seasons (
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
            print(f"   ✅ Temporada '2026' cadastrada/atualizada. ID: {season_id}")
        except Exception as e:
            print(f"   ❌ Erro ao cadastrar temporada: {e}")
            return

    await pool.close()
    print("\n" + "=" * 80)
    print("  CONSOLIDAÇÃO E SETUP CONCLUÍDOS COM SUCESSO!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_setup())
