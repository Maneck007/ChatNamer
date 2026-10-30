# -*- coding: utf-8 -*-
"""报告与改名记录。"""
import datetime
import json
import os


def _plans_dict(p):
    s = p.session
    return {'sid': s.sid, 'old_title': s.title, 'new_title': p.new_title,
            'method': p.method, 'confident': p.confident, 'reason': p.reason,
            'created': datetime.datetime.fromtimestamp(s.created_ms / 1000).strftime('%Y-%m-%d %H:%M'),
            'note': s.note}


def as_row_data(r):
    """PlanItem 或 适配器结果 dict → 统一字段名。"""
    if isinstance(r, dict):
        return {'sid': r.get('sid', ''), 'old_title': r.get('old_title', r.get('old', '')),
                'new_title': r.get('new_title', r.get('new', '')), 'method': r.get('method', ''),
                'confident': r.get('confident', True), 'reason': r.get('reason', ''),
                'created': r.get('created', ''), 'note': r.get('note', ''),
                'verified': r.get('verified', '')}
    return _plans_dict(r)


def write_reports(root, data_by_platform, apply: bool):
    ts = datetime.datetime.now()
    stamp = ts.strftime('%Y%m%d_%H%M%S')
    rec_dir = os.path.join(root, 'records')
    os.makedirs(rec_dir, exist_ok=True)

    record = {
        '工具': 'ChatNamer',
        '时间': ts.strftime('%Y-%m-%d %H:%M:%S'),
        '模式': 'apply' if apply else 'scan',
        '平台': {},
    }
    for name, d in data_by_platform.items():
        entry = dict(d)
        for key in ('plan', 'skipped', 'renamed'):
            if key in entry:
                entry[key] = [as_row_data(r) for r in entry[key]]
        record['平台'][name] = entry

    jpath = os.path.join(rec_dir, f'ChatNamer_记录_{stamp}.json')
    with open(jpath, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # Markdown 报告
    lines = [f"# ChatNamer {'改名' if apply else '扫描'}报告 {ts.strftime('%Y-%m-%d %H:%M')}", '']
    for name, d in data_by_platform.items():
        lines.append(f"## {name}")
        if 'error' in d:
            lines.append(f"- 出错：{d['error']}")
            continue
        lines.append(f"- 扫描 {d.get('scanned', 0)} 条，待处理 {d.get('pending', 0)} 条")
        if d.get('notes'):
            lines.append(f"- 说明：{d['notes']}")

        def as_row(r):
            return as_row_data(r)

        for key, label in (('renamed', '已改名'), ('plan', '计划改名'), ('skipped', '未处理（留给 AI 精修）')):
            rows = [as_row(r) for r in (d.get(key) or [])]
            if rows:
                lines.append(f"\n### {label}（{len(rows)}）\n")
                lines.append('| 原标题 | 新标题 | 方式 |')
                lines.append('|---|---|---|')
                for r in rows:
                    old = (r['old_title'] or '').replace('|', '/')[:40]
                    new = (r.get('new_title') or '').replace('|', '/')[:40]
                    lines.append(f"| {old} | {new} | {r['method']} |")
        lines.append('')
    mpath = os.path.join(rec_dir, f'ChatNamer_报告_{stamp}.md')
    with open(mpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return jpath, mpath
