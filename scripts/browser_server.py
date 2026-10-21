"""Isolated offline browser-test server. Never changes the application .env."""
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['AGENT_MODE']='fixture'
os.environ['LANGSMITH_TRACING']='false'
os.environ.pop('OPENROUTER_API_KEY',None)

if __name__=='__main__':
    import uvicorn
    with tempfile.TemporaryDirectory(prefix='routerescue-browser-') as temporary:
        os.environ['DATABASE_PATH']=str(Path(temporary)/'browser.sqlite3')
        uvicorn.run('apps.api.main:app',host='127.0.0.1',port=8011)
