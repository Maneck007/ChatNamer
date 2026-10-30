import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cli
from chatnamer import core
from chatnamer.platforms import codex, qoder, zcode


class ChatNamerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def database(self, name, script):
        path = self.root / name
        with contextlib.closing(sqlite3.connect(path)) as con, con:
            con.executescript(script)
        return str(path)

    def zcode_fixture(self, include_task=True):
        db = self.database('cli.sqlite', '''
            CREATE TABLE session(id TEXT PRIMARY KEY,title TEXT,title_source TEXT,
              time_created INTEGER,time_updated INTEGER,directory TEXT,time_deleted INTEGER,
              parent_id TEXT,task_type TEXT,time_title_updated INTEGER);
            INSERT INTO session VALUES('s','标题','custom',1000,1000,'',NULL,NULL,NULL,0);
            CREATE TABLE message(id TEXT,session_id TEXT,sequence INTEGER,data TEXT);
            CREATE TABLE part(message_id TEXT,data TEXT);
            INSERT INTO message VALUES('a','s',0,'{"role":"assistant"}');
            INSERT INTO part VALUES('a','{"type":"text","text":"assistant noise"}');
            INSERT INTO message VALUES('u','s',1,'{"role":"user"}');
            INSERT INTO part VALUES('u','{"type":"text","text":"真实用户需求"}');
        ''')
        ui = self.database('ui.sqlite', '''
            CREATE TABLE tasks(task_id TEXT,title TEXT,cli_title TEXT,
              cli_title_source TEXT,title_overridden INTEGER,updated_at INTEGER);
        ''')
        if include_task:
            with contextlib.closing(sqlite3.connect(ui)) as con, con:
                # One session may appear in multiple workspace rows.
                con.executemany('INSERT INTO tasks VALUES(?,?,?,?,?,?)',
                                [('s','标题','标题','custom',0,0)] * 2)
        cfg = {'platforms': {'zcode': {'cli_db': db, 'tasks_index': ui}}}
        ad = zcode.Adapter(cfg, str(self.root))
        item = core.PlanItem(ad.discover()[0], '20261030_标题', 'existing', True)
        backup = self.root / 'backup'
        backup.mkdir()
        return ad, item, db, ui, str(backup)

    def test_zcode_updates_and_verifies_both_databases(self):
        ad, item, db, ui, backup = self.zcode_fixture()
        results = ad.apply([item], backup)
        self.assertTrue(results[0]['verified'])
        self.assertEqual(results[0]['tasks_rows'], 2)
        with contextlib.closing(sqlite3.connect(Path(backup) / 'zcode_cli.sqlite.bak')) as con, con:
            self.assertEqual(con.execute('SELECT title FROM session').fetchone()[0], '标题')

    def test_missing_ui_row_rolls_back_cli_change(self):
        ad, item, db, ui, backup = self.zcode_fixture(False)
        with self.assertRaises(RuntimeError):
            ad.apply([item], backup)
        with contextlib.closing(sqlite3.connect(db)) as con, con:
            self.assertEqual(con.execute('SELECT title FROM session').fetchone()[0], '标题')

    def test_changed_title_is_not_overwritten(self):
        ad, item, db, ui, backup = self.zcode_fixture()
        with contextlib.closing(sqlite3.connect(db)) as con, con:
            con.execute("UPDATE session SET title='另一个新标题'")
        with self.assertRaises(RuntimeError):
            ad.apply([item], backup)
        with contextlib.closing(sqlite3.connect(ui)) as con, con:
            self.assertEqual(con.execute('SELECT DISTINCT title FROM tasks').fetchall(), [('标题',)])

    def test_zcode_summary_uses_user_message(self):
        ad, *_ = self.zcode_fixture()
        self.assertEqual(ad.first_texts(['s']), {'s': '真实用户需求'})

    def test_missing_zcode_path_does_not_create_database(self):
        missing = self.root / 'missing.sqlite'
        ad = zcode.Adapter({'platforms': {'zcode': {'cli_db': str(missing)}}}, str(self.root))
        with self.assertRaises(sqlite3.OperationalError):
            ad.discover()
        self.assertFalse(missing.exists())

    def test_backups_are_unique_and_preserved(self):
        cfg = {'general': {'backup_dir': str(self.root / 'backups')}}
        a = Path(cli.backup_dir(cfg))
        (a / 'original.txt').write_text('old')
        b = Path(cli.backup_dir(cfg))
        self.assertNotEqual(a, b)
        self.assertEqual((a / 'original.txt').read_text(), 'old')

    def test_active_and_excluded_sessions_are_skipped_in_preview(self):
        now = 100000000
        rows = [core.SessionInfo('zcode', sid, '标题', 'custom', 1000, updated)
                for sid, updated in [('old', 1000), ('active', now), ('excluded', 1000)]]
        adapter = mock.Mock()
        adapter.discover.return_value = rows
        adapter.first_texts.return_value = {}
        adapter.notes.return_value = ''
        cfg = {'general': {'active_window_minutes': 60, 'summary_max_len': 24, 'exclude_ids': ['excluded']}}
        with mock.patch.dict(cli.ADAPTERS, {'zcode': mock.Mock(return_value=adapter)}), mock.patch('cli.time.time', return_value=now / 1000):
            out = cli.process_platform('zcode', cfg, False, {})
        self.assertEqual([i.session.sid for i in out['plan']], ['old'])
        adapter.apply.assert_not_called()

    def test_codex_preserves_original_message_and_internal_threads(self):
        db = self.database('state_5.sqlite', '''
            CREATE TABLE threads(id TEXT,name TEXT,title TEXT,created_at_ms INTEGER,
              updated_at_ms INTEGER,cwd TEXT,thread_source TEXT);
            INSERT INTO threads VALUES('u','旧名','原始消息',1000,1000,'','agent_created_thread');
            INSERT INTO threads VALUES('i','内部','内部消息',1000,1000,'','guardian_review');
        ''')
        ad = codex.Adapter({'platforms': {'codex': {'home': str(self.root)}}}, str(self.root))
        found = ad.discover()
        self.assertEqual([s.sid for s in found], ['u'])
        (self.root / 'backup').mkdir()
        result = ad.apply([core.PlanItem(found[0], '20261030_新名', 'existing', True)], str(self.root / 'backup'))
        self.assertTrue(result[0]['verified'])
        with contextlib.closing(sqlite3.connect(db)) as con, con:
            self.assertEqual(con.execute("SELECT title FROM threads WHERE id='u'").fetchone()[0], '原始消息')
        self.assertEqual(json.loads((self.root / 'session_index.jsonl').read_text(encoding='utf-8'))['thread_name'], '20261030_新名')

    def test_qoder_updates_title_and_preserves_other_fields(self):
        db = self.database('main.sqlite', '''
            CREATE TABLE chat_sessions(session_id TEXT,title TEXT,created_at INTEGER,
              updated_at INTEGER,cwd TEXT,session_kind TEXT,deleted_at INTEGER);
            INSERT INTO chat_sessions VALUES('s','旧名',1000,2000,'','chat',NULL);
            INSERT INTO chat_sessions VALUES('d','已删除',1000,2000,'','chat',1);
        ''')
        ad = qoder.Adapter({'platforms': {'qoder': {'data_dir': str(self.root)}}}, str(self.root))
        found = ad.discover()
        self.assertEqual([s.sid for s in found], ['s'])
        (self.root / 'backup').mkdir()
        result = ad.apply([core.PlanItem(found[0], '20261030_新名', 'existing', True)], str(self.root / 'backup'))
        self.assertTrue(result[0]['verified'])
        with contextlib.closing(sqlite3.connect(db)) as con, con:
            self.assertEqual(con.execute("SELECT updated_at FROM chat_sessions WHERE session_id='s'").fetchone()[0], 2000)

    def test_lock_does_not_replace_another_instance(self):
        with mock.patch.object(cli, 'ROOT', str(self.root)):
            cli.acquire_lock()
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                cli.acquire_lock()
            cli.release_lock()

    def test_default_configuration_is_opt_in(self):
        cfg = core.load_config(str(Path(__file__).resolve().parents[1]))
        self.assertTrue(all(not p['enabled'] for p in cfg['platforms'].values()))
        self.assertFalse(cfg['platforms']['codex']['home'].startswith('~'))


if __name__ == '__main__':
    unittest.main()
