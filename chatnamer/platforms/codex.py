# -*- coding: utf-8 -*-
"""Codex 适配器：改 state_5.sqlite 的 threads.name，并同步追加 session_index.jsonl。

- 权威显示名 = threads.name（Codex Desktop 侧边栏/resume 列表）
- 摘要来源 = threads.first_user_message（threads.title 是原始首条消息，不动）
- 用户可见 = thread_source ∈ {user, NULL, agent_created_thread}（含归档）；
  guardian_review/subagent 是隐藏内部会话，排除
- session_index.jsonl 为追加式索引（同 id 可多行，最后一行为准），追加保持与库一致
"""
import json
import os
import shutil
import sqlite3
import time

from chatnamer.core import SessionInfo, is_junk
from chatnamer.platforms.base import Adapter as BaseAdapter

NOW = lambda: int(time.time() * 1000)


class Adapter(BaseAdapter):
    name = 'codex'

    def _db(self):
        return os.path.join(self.pcfg['home'], 'state_5.sqlite')

    def _index(self):
        return os.path.join(self.pcfg['home'], 'session_index.jsonl')

    def discover(self):
        con = sqlite3.connect('file:%s?mode=ro' % self._db(), uri=True, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        try:
            # 用户可见：user / NULL / agent_created_thread（会出现在侧边栏）；
            # 含归档（archived=1）也统一命名；guardian_review/subagent 为隐藏内部会话，排除
            rows = con.execute("""
                SELECT id, coalesce(name,''), 'generated', created_at_ms, updated_at_ms,
                       coalesce(cwd,''), thread_source
                FROM threads
                WHERE (thread_source='user' OR thread_source IS NULL
                       OR thread_source='agent_created_thread')
            """).fetchall()
        finally:
            con.close()
        return [SessionInfo('codex', r[0], r[1], r[2], r[3] or 0, r[4] or 0, r[5], str(r[6]))
                for r in rows]

    def first_texts(self, sids):
        con = sqlite3.connect('file:%s?mode=ro' % self._db(), uri=True, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        out = {}
        try:
            for i in range(0, len(sids), 50):
                chunk = sids[i:i + 50]
                q = ','.join('?' * len(chunk))
                rows = con.execute(
                    f"SELECT id, first_user_message, rollout_path FROM threads WHERE id IN ({q})",
                    chunk).fetchall()
                for sid, t, rp in rows:
                    t = (t or '').strip()
                    if t and not is_junk(t) and not t.startswith('/'):
                        out[sid] = t[:600]
                    else:
                        # 空名/命令开头的会话：解压 rollout 找真实首条用户消息
                        txt = self._text_from_rollout(rp)
                        if txt:
                            out[sid] = txt
        finally:
            con.close()
        return out

    @staticmethod
    def _text_from_rollout(rollout_path):
        if not rollout_path:
            return ''
        p = rollout_path.replace('\\\\?\\', '')
        if not os.path.exists(p) and os.path.exists(p + '.zst'):
            p = p + '.zst'
        if not os.path.exists(p):
            return ''
        try:
            if p.endswith('.zst'):
                import zstandard as zstd
                with open(p, 'rb') as f:
                    text = zstd.ZstdDecompressor().stream_reader(f).read().decode('utf-8', 'replace')
            else:
                with open(p, encoding='utf-8', errors='replace') as f:
                    text = f.read()
        except Exception:
            return ''
        import re
        for line in text.splitlines():
            try:
                pl = json.loads(line).get('payload', {})
            except Exception:
                continue
            if pl.get('type') != 'user_message' and not (
                    pl.get('type') == 'message' and pl.get('role') == 'user'):
                continue
            t = pl.get('message') or ''
            if isinstance(pl.get('content'), list):
                t = ' '.join(str(c.get('text', '')) for c in pl['content'] if isinstance(c, dict))
            t = re.sub(r'<[^>]+>', '', t or '').strip()
            if t and len(t) > 5 and not t.startswith('<') and not t.startswith('/'):
                return t[:600]
        return ''

    def apply(self, items, backup_dir):
        import datetime
        db = self._db()
        # 备份
        bak = os.path.join(backup_dir, 'codex_state_5.sqlite.bak')
        s, d = sqlite3.connect(db), sqlite3.connect(bak)
        s.backup(d)
        d.close()
        s.close()
        idx = self._index()
        if os.path.exists(idx):
            shutil.copy2(idx, os.path.join(backup_dir, 'codex_session_index.jsonl.bak'))

        con = sqlite3.connect(db, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        results = []
        try:
            con.execute('BEGIN IMMEDIATE')
            for it in items:
                con.execute('UPDATE threads SET name=? WHERE id=?',
                            (it.new_title, it.session.sid))
                results.append({'sid': it.session.sid, 'old': it.session.title,
                                'new': it.new_title, 'method': it.method})
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

        # 追加 session_index.jsonl
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds')
        with open(idx, 'a', encoding='utf-8') as f:
            for r in results:
                f.write(json.dumps({'id': r['sid'], 'thread_name': r['new'],
                                    'updated_at': now_iso}, ensure_ascii=False) + '\n')

        # 复核
        con = sqlite3.connect('file:%s?mode=ro' % db, uri=True, timeout=10)
        try:
            for r in results:
                row = con.execute('SELECT name FROM threads WHERE id=?', (r['sid'],)).fetchone()
                r['verified'] = bool(row and row[0] == r['new'])
        finally:
            con.close()
        return results

    def notes(self):
        return ("用户可见会话含 agent_created_thread 与归档会话；仅排除 guardian_review/subagent 内部会话；"
                "写 threads.name 并追加 session_index.jsonl")
