"""Bounded live OpenRouter/MCP/LangSmith verification using synthetic test data."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from routerescue.config import runtime_status
from fastapi.testclient import TestClient
from apps.api.main import app
from langsmith import Client
from langsmith.run_trees import get_cached_client
from langchain_core.tracers.langchain import wait_for_all_tracers


def main():
    status=runtime_status()
    if not status['agent_available']:
        raise SystemExit('OpenRouter is not configured for a live run.')
    with tempfile.TemporaryDirectory(prefix='routerescue-live-') as temporary:
        os.environ['DATABASE_PATH']=str(Path(temporary)/'live.sqlite3')
        with TestClient(app) as client:
            login=client.post('/api/auth/login',json={'email':'aarav@routerescue.local','password':'Aarav@12345'})
            assert login.status_code==200
            trip=client.get('/api/trips').json()
            trip=next(t for t in trip if t['scenario']=='flight')
            client.post(f"/api/trips/{trip['id']}/events",json={'event_type':'FLIGHT_CANCELLED','source_event_id':'live-verification','description':'My flight has been cancelled. I am in Mangaluru and can leave from 08:00. Please find alternatives within my budget.','available_from':'2026-11-15T08:00:00+05:30'})
            response=client.post(f"/api/trips/{trip['id']}/recoveries")
            assert response.status_code==202,response.status_code
            run=response.json()
            for _ in range(125):
                run=client.get('/api/recoveries/'+run['id']).json()
                if run['state']!='RUNNING': break
                time.sleep(1)
            wait_for_all_tracers()
            get_cached_client().flush()
            remote=None
            for _ in range(4):
                try:
                    remote=Client().read_run(run['id'],load_child_runs=True)
                    break
                except Exception:
                    time.sleep(2)
            summary={'run_id':run['id'],'state':run['state'],'agent':run.get('agent'),'recommended_option_id':run.get('recommended_option_id'),'error':run.get('error'),'langsmith_received':remote is not None,'trace_url':remote.url if remote else None,'remote_child_spans':len(remote.child_runs or []) if remote else 0}
            (ROOT/'artifacts').mkdir(exist_ok=True)
            (ROOT/'artifacts/live-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            print(json.dumps(summary,indent=2))
            return 0 if run['state']=='OPTIONS_READY' and remote is not None else 1


if __name__=='__main__':
    raise SystemExit(main())
