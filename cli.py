#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ChatNamer CLI —— 对话标题统一命名（yyyymmdd_内容概括）。

用法：
  python cli.py                        # 全平台扫描（只读，输出计划与报告）
  python cli.py --apply                # 全平台执行改名（自动备份）
  python cli.py --platform zcode --apply
  python cli.py --apply --summaries summaries.json   # AI 精修轮：带外部摘要
  python cli.py --export-pending pending.json        # 导出待精修会话上下文
"""
import argparse
import json
import os
import sys
import time
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatnamer import core, report
from chatnamer.platforms import claude, codex, qoder, zcode

ROOT = os.path.dirname(os.path.abspath(__file__))
ADAPTERS = {'zcode': zcode.Adapter, 'codex': codex.Adapter,
            'qoder': qoder.Adapter, 'claude': claude.Adapter}
ALL = ['zcode', 'codex', 'qoder', 'claude']


def backup_dir(cfg):
    d = cfg['general'].get('backup_dir') or os.path.join(
        os.environ.get('TEMP', ROOT), 'ChatNamer_backups')
    os.makedirs(d, exist_ok=True)
    return tempfile.mkdtemp(prefix=time.strftime('%Y%m%d_%H%M%S_'), dir=d)


def acquire_lock():
    lock = os.path.join(ROOT, '.lock')
    try:
        with open(lock, 'x') as f:
            f.write(str(os.getpid()))
    except FileExistsError:
        print('[ChatNamer] .lock 已存在；确认没有运行中的实例后再删除该文件')
        sys.exit(1)


def release_lock():
    try:
        os.remove(os.path.join(ROOT, '.lock'))
    except OSError:
        pass


def process_platform(name, cfg, apply, summaries):
    ad = ADAPTERS[name](cfg, ROOT)
    sessions = ad.discover()
    window = cfg['general']['active_window_minutes'] * 60 * 1000
    excluded = set(cfg['general'].get('exclude_ids', []))
    now = int(time.time() * 1000)
    pending = [s for s in sessions
               if not core.is_formatted(s.title)
               and now - (s.updated_ms or 0) >= window
               and s.sid not in excluded]
    items = []
    if pending:
        texts = ad.first_texts([s.sid for s in pending])
        for s in pending:
            items.append(core.propose(s, texts.get(s.sid, ''),
                                      cfg['general']['summary_max_len'], summaries))
    todo = [i for i in items if i.confident and i.new_title]
    skipped = [i for i in items if not (i.confident and i.new_title)]
    out = {'scanned': len(sessions), 'pending': len(pending), 'notes': ad.notes()}
    if apply and todo:
        out['renamed'] = ad.apply(todo, backup_dir(cfg))
    elif apply:
        out['renamed'] = []
    if not apply:
        out['plan'] = todo
    out['skipped'] = skipped
    return out


def main():
    ap = argparse.ArgumentParser(description='ChatNamer 对话标题统一命名')
    ap.add_argument('--platform', default='all',
                    help='all 或 zcode,codex,qoder,claude 组合')
    ap.add_argument('--apply', action='store_true', help='执行写入（默认只扫描）')
    ap.add_argument('--summaries', help='外部摘要 JSON（{"platform":{sid:摘要}}）')
    ap.add_argument('--export-pending', help='把待精修会话（含上下文）导出为 JSON')
    ap.add_argument('--quiet', action='store_true', help='只输出摘要行')
    ap.add_argument('--no-report', action='store_true', help='不写 records 报告')
    args = ap.parse_args()

    cfg = core.load_config(ROOT)
    names = ALL if args.platform == 'all' else [x.strip() for x in args.platform.split(',')]
    for n in names:
        if n not in ADAPTERS:
            print(f'未知平台: {n}')
            sys.exit(2)

    if not any(cfg['platforms'].get(n, {}).get('enabled', False) for n in names):
        print('尚未启用平台：复制 config.example.json 为 config.json，检查路径并设置 enabled=true。')
        return 0

    summaries = core.load_summaries(args.summaries)
    if args.apply:
        acquire_lock()
    data = {}
    try:
        for name in names:
            if not cfg['platforms'].get(name, {}).get('enabled', False):
                continue
            try:
                data[name] = process_platform(name, cfg, args.apply, summaries)
            except Exception as e:
                data[name] = {'error': f'{type(e).__name__}: {e}'}
            d = data[name]
            if 'error' in d:
                print(f'[{name}] 出错：{d["error"]}')
            else:
                n_ok = len(d.get('renamed', []) or [])
                print(f'[{name}] 扫描 {d["scanned"]}，待处理 {d["pending"]}，'
                      f'{"已改名" if args.apply else "计划改名"} {n_ok if args.apply else len(d.get("plan", []))}'
                      + (f'，留精修 {len(d.get("skipped", []))}' if d.get('skipped') else ''))
                if not args.quiet:
                    def _row(r):
                        if isinstance(r, dict):
                            # 适配器返回 {sid, old, new, method}；报告结构为 {old_title, new_title, method}
                            return (r.get('old_title', r.get('old', '')),
                                    r.get('new_title', r.get('new', '')),
                                    r.get('method', ''))
                        return r.session.title, r.new_title, r.method
                    for key in ('renamed', 'plan'):
                        for r in d.get(key, []) or []:
                            old, new, method = _row(r)
                            print(f'    {old[:36]} -> {new[:40]} ({method})')
                    for r in d.get('skipped', []) or []:
                        print(f'    [留精修] {r.session.title[:36]} ({r.reason})')
    finally:
        if args.apply:
            release_lock()

    if args.export_pending:
        export = {}
        for name, d in data.items():
            if 'error' in d:
                continue
            m = {}
            for it in (d.get('skipped') or []) + (d.get('plan') or []):
                m[it.session.sid] = {'old_title': it.session.title,
                                     'created': core.date_prefix(it.session.created_ms),
                                     'note': it.session.note, 'reason': it.reason}
            if m:
                export[name] = m
        with open(args.export_pending, 'w', encoding='utf-8') as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        print(f'待精修清单已导出: {args.export_pending}')

    if not args.no_report:
        anything = any((d.get('renamed') or d.get('skipped') or 'error' in d)
                       for d in data.values())
        if anything or not args.apply:
            j, m = report.write_reports(ROOT, data, apply=args.apply)
            print(f'记录: {j}')

    return 1 if any('error' in d or any(not r.get('verified', False)
                   for r in d.get('renamed', [])) for d in data.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
