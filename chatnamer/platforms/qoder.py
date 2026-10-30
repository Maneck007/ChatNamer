# -*- coding: utf-8 -*-
"""Qoder 适配器：改 com.qodercn.app.stable/main.sqlite 的 chat_sessions.title。

- 侧边栏对话列表读 chat_sessions（title / created_at / archived / deleted_at）
- 摘要来源 = chat_session_messages 中 role='user' 的首条 payload_json 文本
"""
import json
import os
import sqlite3

from chatnamer.core import SessionInfo, is_junk
from chatnamer.platforms.base import Adapter as BaseAdapter


class Adapter(BaseAdapter):
    name = 'qoder'

    def _db(self):
        return os.path.join(self.pcfg['data_dir'], 'main.sqlite')

    def discover(self):
        con = sqlite3.connect('file:%s?mode=ro' % self._db(), uri=True, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        try:
            rows = con.execute("""
                SELECT session_id, coalesce(title,''), 'generated',
                       created_at, updated_at, coalesce(cwd,''), session_kind
                FROM chat_sessions WHERE deleted_at IS NULL
            """).fetchall()
        finally:
            con.close()
        return [SessionInfo('qoder', r[0], r[1], r[2], r[3] or 0, r[4] or 0, r[5], str(r[6]))
                for r in rows]

    def first_texts(self, sids):
        con = sqlite3.connect('file:%s?mode=ro' % self._db(), uri=True, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        out = {}
        try:
            for sid in sids:
                rows = con.execute(
                    "SELECT payload_json FROM chat_session_messages "
                    "WHERE session_id=? ORDER BY sequence LIMIT 12",
                    (sid,)).fetchall()
                for (pj,) in rows:
                    try:
                        j = json.loads(pj)
                    except Exception:
                        continue
                    # role 存在 JSON 内而非列；只取真实用户消息，跳过纯附件引用
                    if (j.get('role') or '').lower() != 'user':
                        continue
                    t = (j.get('text') or '').strip()
                    if not t or (t.startswith("'") and t.endswith("'") and '.' in t):
                        continue
                    if is_junk(t):
                        continue
                    out[sid] = t[:600]
                    break
        finally:
            con.close()
        return out

    def apply(self, items, backup_dir):
        db = self._db()
        bak = os.path.join(backup_dir, 'qoder_main.sqlite.bak')
        s, d = sqlite3.connect(db), sqlite3.connect(bak)
        s.backup(d)
        d.close()
        s.close()

        con = sqlite3.connect(db, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        results = []
        try:
            con.execute('BEGIN IMMEDIATE')
            for it in items:
                con.execute('UPDATE chat_sessions SET title=? WHERE session_id=?',
                            (it.new_title, it.session.sid))
                results.append({'sid': it.session.sid, 'old': it.session.title,
                                'new': it.new_title, 'method': it.method})
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

        con = sqlite3.connect('file:%s?mode=ro' % db, uri=True, timeout=10)
        try:
            for r in results:
                row = con.execute('SELECT title FROM chat_sessions WHERE session_id=?',
                                  (r['sid'],)).fetchone()
                r['verified'] = bool(row and row[0] == r['new'])
        finally:
            con.close()
        return results

    def notes(self):
        return '会话数量少；标题在本地 chat_sessions 表，已验证可写'
