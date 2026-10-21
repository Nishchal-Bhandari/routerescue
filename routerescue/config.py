import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if not os.getenv('MCP_OWNER_ID'):
    load_dotenv(ROOT / '.env')


def database_path():
    return Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'routerescue.sqlite3'))).resolve()


def runtime_status():
    mode = os.getenv('AGENT_MODE', 'openrouter')
    key = bool(os.getenv('OPENROUTER_API_KEY'))
    tracing = os.getenv('LANGSMITH_TRACING','false').lower()=='true' and bool(os.getenv('LANGSMITH_API_KEY'))
    return dict(data_mode='SIMULATED', agent_mode=mode, agent_available=mode=='openrouter' and key, model=os.getenv('OPENROUTER_MODEL','openrouter/free'), langsmith_enabled=tracing, langsmith_project=os.getenv('LANGSMITH_PROJECT','routerescue'), provider_mode='Synthetic fixtures', database='SQLite', corridor='Mangaluru → Bengaluru', date='2026-11-15')
