from routerescue import store
from routerescue.service import stage,update_run


def test_superseded_progress_cannot_restore_running_state(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'race.sqlite3'))
    store.initialize()
    run={'id':'run','state':'RUNNING','progress':[]}
    with store.connection() as db:
        db.execute('INSERT INTO trips VALUES(?,?,?)',('trip','owner','{}'))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run','trip','1:1','RUNNING',store.dump(run)))
        store.supersede(db,'trip')
    stage('run','VALIDATED','old worker finished')
    update_run('run',state='OPTIONS_READY')
    with store.connection() as db:
        row=db.execute('SELECT state,body FROM runs WHERE id=?',('run',)).fetchone()
        assert row['state']=='SUPERSEDED'
        assert 'RUNNING' not in row['body']


def test_restart_marks_interrupted_run_failed(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'restart.sqlite3'))
    store.initialize()
    with store.connection() as db:
        db.execute('INSERT INTO trips VALUES(?,?,?)',('trip','owner','{}'))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run','trip','1:1','RUNNING',store.dump({'state':'RUNNING'})))
    store.initialize()
    with store.connection() as db:
        row=db.execute('SELECT state,input_key FROM runs WHERE id=?',('run',)).fetchone()
        assert row['state']=='FAILED' and row['input_key']=='interrupted:run'
