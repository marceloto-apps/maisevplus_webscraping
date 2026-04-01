"""
T08 — FBRef Parser HTML
Extrai Múltiplas Tabelas (Summary, Passing, Possession, Defense, GCA)
Funde em dicts de jogadores, calculando o RAW_JSON e AGGREGATED finale de xG/xAG.
"""
import re
import pandas as pd
from io import StringIO
from typing import Dict, Any, List

from ...db.logger import get_logger

logger = get_logger(__name__)

class FBRefParser:
    """Parser Inteligente e Otimizado de Tabelas HTML FBREF."""

    REQUIRED_TABLES = ['summary', 'passing', 'defense', 'possession', 'gca']
    
    # Campo Segregado por Tabela para evitar colisões entre 'xG' / 'Att' / 'Min' de DataFrames diferentes
    FIELD_MAP_BY_TABLE = {
        'summary': {
            'Player': 'name', 'Min': 'minutes', 'xG': 'xg', 'xAG': 'xag'
        },
        'passing': {
            'Player': 'name', 'PrgP': 'progressive_passes'
        },
        'defense': {
            'Player': 'name', 'Press': 'pressures', 'Tkl': 'tackles', 'Blocks': 'blocks'
        },
        'possession': {
            'Player': 'name', 'Carries': 'carries', 'PrgC': 'progressive_carries'
        },
        'gca': {
            'Player': 'name', 'SCA': 'sca', 'GCA': 'gca'
        }
    }

    @classmethod
    def parse_match(cls, html_content: str) -> Dict[str, Any]:
        """
        Gatilho Mestre. Passa o HTML sujo, retorna pacote limpo pronto para o Backfill:
        {
          "home_players": [...],
          "away_players": [...],
          "aggregated": { "xg_home": X, "xg_away": Y, ...}
        }
        """
        # Desencarcera as tabelas presas dentro de comments do DOM
        uncommented_html = re.sub(r'<!--|-->', '', html_content)
        
        return cls._parse_with_bs4(uncommented_html)

    @classmethod
    def _parse_with_bs4(cls, html: str) -> Dict[str, Any]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        
        # O ID da FBRef não é estritamente puro Hex, pode conter variação alfanumérica mista.
        team_tables = soup.find_all("table", id=re.compile(r"^stats_\w+_summary$"))
        
        if len(team_tables) < 2:
            return {"home_players": [], "away_players": [], "aggregated": {}}

        # Home é sempre o primeiro achado, Away o segundo na página.
        match_home = re.match(r'stats_(.+)_summary', team_tables[0]['id'])
        match_away = re.match(r'stats_(.+)_summary', team_tables[1]['id'])
        
        home_hash_id = match_home.group(1) if match_home else None
        away_hash_id = match_away.group(1) if match_away else None

        if not home_hash_id or not away_hash_id:
             return {"home_players": [], "away_players": [], "aggregated": {}}

        home_players = cls._merge_team_tables(soup, home_hash_id)
        away_players = cls._merge_team_tables(soup, away_hash_id)

        # Monta as chaves Agregadas de Partida para o SQL (Match level)
        aggregated = cls._build_aggregations(home_players, away_players)

        return {
            "home_players": home_players,
            "away_players": away_players,
            "aggregated": aggregated
        }

    @classmethod
    def _merge_team_tables(cls, soup, team_hash: str) -> List[Dict[str, Any]]:
        """Busca Summary, Passing, Defense, Possession e GCA combinando por nome."""
        master_df = None
        
        for table_type in cls.REQUIRED_TABLES:
            table_id = f"stats_{team_hash}_{table_type}"
            table_node = soup.find("table", id=table_id)
            if not table_node:
                continue

            # Joga pro pandas ler bonitão aquele tranco html isolado
            # Passamos via StringIO para o Pandas (evitando parse como file_path em versões novas lxml baseadas)
            df_list = pd.read_html(StringIO(str(table_node)))
            if not df_list:
                continue
            
            df = df_list[0]
            
            # Limpa e filtra o df para ter a estrutura plana puxando unicamente as métricas que cobiçamos
            df = cls._normalize_headers(df, table_type)
            
            # Drop da linha de Totais (Player == X Players) para não estourar cast
            if 'name' in df.columns:
                df = df[~df['name'].str.contains('Players', case=False, na=False)]
            
            # Adiciona ao merge consolidado
            if master_df is None:
                master_df = df
            else:
                cols_to_use = df.columns.difference(master_df.columns).to_list() + ['name']
                master_df = master_df.merge(df[cols_to_use], on='name', how='outer')

        if master_df is None or master_df.empty:
            return []

        # Limpeza blindada:
        # Primeiro joga jogadores que falharam no outer merge pelo espaço fora.
        master_df = master_df.dropna(subset=['name'])
        
        # Depois garante preencher com ZERO os buracos apenas dos tipos numéricos (pra não fuder o 'name').
        numeric_cols = master_df.select_dtypes(include='number').columns
        master_df[numeric_cols] = master_df[numeric_cols].fillna(0)
        
        return master_df.to_dict(orient='records')

    @classmethod
    def _normalize_headers(cls, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            flat_headers = []
            for col in df.columns:
                level_1 = col[1] if len(col) > 1 else col[0]
                # Edge case da porra do pandas gerando 'Unnamed: X_level_Y' em sub-headers fakes
                if 'Unnamed' in str(level_1):
                    flat_headers.append(col[0])
                else:
                    flat_headers.append(level_1)
            df.columns = flat_headers
            
        field_map = cls.FIELD_MAP_BY_TABLE.get(table_type, {})
        df_renamed = df.rename(columns=field_map)
        
        # Puxa apenas os values do target table específico
        target_cols = [c for c in field_map.values() if c in df_renamed.columns]
        
        clean_df = df_renamed[target_cols].copy()
        
        for col in target_cols:
            if col != 'name':
                clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')

        return clean_df

    @classmethod
    def _build_aggregations(cls, home_players: List[Dict], away_players: List[Dict]) -> Dict[str, Any]:
        """ Soma agressiva de propriedades para espelhar as colunas Match-Level M2 """
        def sum_metric(players: List[Dict], metric: str) -> float:
            return round(sum([float(p.get(metric, 0) or 0) for p in players]), 2)
            
        return {
            "xg_home": sum_metric(home_players, "xg"),
            "xg_away": sum_metric(away_players, "xg"),
            "total_pressures_home": int(sum_metric(home_players, "pressures")),
            "total_pressures_away": int(sum_metric(away_players, "pressures")),
            "progressive_passes_home": int(sum_metric(home_players, "progressive_passes")),
            "progressive_passes_away": int(sum_metric(away_players, "progressive_passes"))
        }

