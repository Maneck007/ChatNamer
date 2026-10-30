# -*- coding: utf-8 -*-
"""ZCode 适配器：双库改名。

标题存两处，必须同时写，否则 UI 不更新：
  A. CLI 库 <home>\\.zcode\\cli\\db\\db.sqlite 的 session 表
  B. UI 库 tasks-index.sqlite 的 tasks 表（侧边栏读它的 title）
"""
import json
import os
import sqlite3
import time
from pathlib import Path

from chatnamer.core import SessionInfo
from chatnamer.platforms.base import Adapter as BaseAdapter

NOW = lambda: int(time.time() * 1000)


class Adapter(BaseAdapter):
    name = 'zcode'

    def _connect(self, path):
        # mode=rw refuses to create a new, empty database on a mistyped path.
        con = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=rw', uri=True, timeout=10)
        con.execute('PRAGMA busy_timeout=10000')
        return con

    def discover(self):
        con = self._connect(self.pcfg['cli_db'])
        try:
            rows = con.execute("""
                SELECT id, title, title_source, time_created, time_updated, directory
                FROM session
                WHERE time_deleted IS NULL AND (parent_id IS NULL OR task_type='fork')
            """).fetchall()
        finally:
            con.close()
        return [SessionInfo('zcode', r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]

    def first_texts(self, sids):
        con = self._connect(self.pcfg['cli_db'])
        out = {}
        try:
            for i in range(0, len(sids), 50):
                chunk = sids[i:i + 50]
                q = ','.join('?' * len(chunk))
                rows = con.execute(f"""
                    SELECT m.session_id, p.data FROM message m
                    JOIN part p ON p.message_id = m.id
                    WHERE m.session_id IN ({q})
                      AND json_extract(m.data, '$.role')='user'
                    ORDER BY m.session_id, m.sequence
                """, chunk).fetchall()
                for sid, pdata in rows:
                    if sid in out:
                        continue
                    try:
                        pj = json.loads(pdata)
                    except Exception:
                        continue
                    if pj.get('type') != 'text':
                        continue
                    t = (pj.get('text') or '').strip()
                    if not t:
                        continue
                    from chatnamer.core import is_junk
                    if is_junk(t):
                        continue
                    out[sid] = t[:600]
        finally:
            con.close()
        return out

    def apply(self, items, backup_dir):
        from chatnamer.core import PlanItem
        now = NOW()
        cli_db = self.pcfg['cli_db']
        tasks_index = self.pcfg['tasks_index']
        results = []

        # 备份
        for src in (cli_db, tasks_index):
            dst = os.path.join(backup_dir, f'zcode_{os.path.basename(src)}.bak')
            s, d = self._connect(src), sqlite3.connect(dst)
            s.backup(d)
            d.close()
            s.close()

        con = self._connect(cli_db)
        try:
            if not os.path.isfile(tasks_index):
                raise FileNotFoundError(tasks_index)
            con.execute('ATTACH DATABASE ? AS ui', (tasks_index,))
            con.execute('BEGIN IMMEDIATE')
            for it in items:
                sid, new = it.session.sid, it.new_title
                cur = con.execute(
                    "UPDATE session SET title=?, title_source='custom', "
                    "time_title_updated=? WHERE id=? AND title IS ?", (new, now, sid, it.session.title))
                if cur.rowcount != 1:
                    raise RuntimeError(f'会话不存在或预览后标题已变化：{sid}')
                r = {'sid': sid, 'old': it.session.title, 'new': new, 'method': it.method}
                cur = con.execute(
                    "UPDATE ui.tasks SET title=?, cli_title=?, "
                    "cli_title_source='custom', title_overridden=1, updated_at=? "
                    "WHERE task_id=?", (new, new, now, sid))
                if cur.rowcount < 1:
                    raise RuntimeError(f'UI 索引缺少会话，整批撤销：{sid}')
                r['tasks_rows'] = cur.rowcount
                results.append(r)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

        # 复核
        con = self._connect(cli_db)
        try:
            con.execute('ATTACH DATABASE ? AS ui', (tasks_index,))
            for r in results:
                row = con.execute('SELECT title FROM session WHERE id=?', (r['sid'],)).fetchone()
                ui = con.execute('SELECT title,cli_title,title_overridden FROM ui.tasks WHERE task_id=?', (r['sid'],)).fetchall()
                r['verified'] = bool(row and row[0] == r['new'] and ui and
                                     all(t == (r['new'], r['new'], 1) for t in ui))
        finally:
            con.close()
        return results

    def notes(self):
        return '排除子代理会话；双库（session 表 + tasks 表）同步写入'
