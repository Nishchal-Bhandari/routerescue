"""Portable project commands. Run with the project virtual environment."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)


def run(args,cwd=ROOT):
    subprocess.run(args,cwd=cwd,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','test','seed','reset-demo','package','smoke-agent'])
    args=parser.parse_args()
    if args.command=='run':
        run([sys.executable,'-m','uvicorn','apps.api.main:app','--host','127.0.0.1','--port','8000'])
    elif args.command=='test': run([sys.executable,'-m','pytest','-q'])
    elif args.command=='seed':
        from routerescue.store import initialize
        from routerescue.providers.fixtures import offers
        initialize()
        print(f'SQLite initialized; {len(offers())} versioned flight candidates available. Each browser session receives its own seeded trip on first load.')
    elif args.command=='reset-demo':
        from routerescue.config import database_path
        from datetime import datetime,timezone
        path=database_path()
        if path.parent!=ROOT/'data': raise SystemExit('Reset is limited to the local data/ directory. Stop the server first.')
        backup=path.parent/('backup-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
        backup.mkdir(parents=True)
        for name in (path.name,path.name+'-wal',path.name+'-shm','agent-checkpoints.sqlite3','agent-checkpoints.sqlite3-wal','agent-checkpoints.sqlite3-shm'):
            file=path.parent/name
            if file.exists(): file.rename(backup/name)
        print(f'Previous demo data preserved in {backup}. Restart the server and reload the browser.')
    elif args.command=='package':
        target=ROOT/'artifacts'/'RouteRescue-submission.zip';target.parent.mkdir(exist_ok=True)
        ignored={'.git','.venv','node_modules','dist','__pycache__','.pytest_cache','data','test-results','playwright-report','artifacts'}
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for current,folders,files in os.walk(ROOT):
                folders[:]=[folder for folder in folders if folder not in ignored]
                for name in files:
                    file=Path(current)/name
                    if name!='.env' and file.suffix not in ('.log','.tsbuildinfo'):
                        archive.write(file,file.relative_to(ROOT))
        print(target)
    elif args.command=='smoke-agent':
        run([sys.executable,str(ROOT/'scripts'/'verify_live.py')])


if __name__=='__main__': main()
