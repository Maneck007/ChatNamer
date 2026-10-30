# -*- coding: utf-8 -*-
"""ChatNamer 核心逻辑：格式规则、扫描计划、摘要生成。"""
import datetime
import json
import os
import re
from dataclasses import dataclass

TITLE_RE = re.compile(r'^\d{8}_\S')
DATE_RE = re.compile(r'^\d{8}')

# 各平台注入的系统文本，不算真实用户输入
JUNK_PREFIXES = (
    '<system-reminder', 'Available agent types', 'The TodoWrite', '<command-',
    'Caveat:', '<task-notification', '<system-warning', '[Request interrupted',
    '# Shared conversation', '<bash-', 'This session is being continued',
)
# 摘要中的通用噪音词
NOISE_PHRASES = (
    'Files mentioned by the user:', 'codex-clipboard', '帮我看看这个', '帮我看看',
    '请帮我', '帮我', '麻烦', '请', '我想要', '我要', '现在需要', '现在',
    '你是执行者。', '你是执行者，', '你是执行者',
)


@dataclass
class SessionInfo:
    platform: str
    sid: str
    title: str
    title_source: str
    created_ms: int
    updated_ms: int
    cwd: str = ''
    note: str = ''


@dataclass
class PlanItem:
    session: SessionInfo
    new_title: str
    method: str            # existing | heuristic | llm
    confident: bool
    reason: str = ''


def is_formatted(title: str) -> bool:
    return bool(TITLE_RE.match(title or ''))


def date_prefix(ms: int) -> str:
    return datetime.datetime.fromtimestamp(ms / 1000).strftime('%Y%m%d')


def clean_text(t: str) -> str:
    if not t:
        return ''
    t = re.sub(r'[A-Za-z]:[\\/][^\s，。；）」』"\'<>|]*', '', t)   # 盘符路径
    t = re.sub(r'\\\\[\w.?\\-]+', '', t)                          # UNC 路径
    t = re.sub(r'https?://\S+', '', t)
    for p in NOISE_PHRASES:
        t = t.replace(p, ' ')
    t = re.sub(r'[#*`>\[\]|\\]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t.strip(' 　，。；：、-—*()（）"\'')


def is_junk(text: str) -> bool:
    t = (text or '').lstrip()
    return (not t) or any(t.startswith(p) for p in JUNK_PREFIXES)


def heuristic_summary(text: str, max_len: int = 24) -> str:
    t = clean_text(text)
    return t[:max_len].strip() if t else ''


def propose(session: SessionInfo, first_text: str = '', max_len: int = 24,
            summaries: dict = None) -> PlanItem:
    """为一条会话生成新标题方案。"""
    date = date_prefix(session.created_ms)
    if summaries and session.sid in summaries:
        s = clean_text(str(summaries[session.sid]))[:max_len]
        return PlanItem(session, f'{date}_{s}' if s else '', 'llm', bool(s), '外部摘要覆盖')

    src = (session.title_source or '').lower()
    existing = re.sub(r'^(Fork of |来自分享：)', '', clean_text(session.title or ''))
    if existing.lower() in ('untitled', '新对话', 'new chat', '未命名'):
        existing = ''
    if src in ('generated', 'custom') and existing and not DATE_RE.match(existing):
        return PlanItem(session, f'{date}_{existing[:max_len]}', 'existing', True,
                        '沿用原标题加日期前缀')
    s = heuristic_summary(first_text, max_len)
    if s and len(s) >= 4:
        return PlanItem(session, f'{date}_{s}', 'heuristic', True, '首条用户消息提取')
    return PlanItem(session, '', 'manual', False, '无把握：留给 AI 精修轮')


def load_config(root: str) -> dict:
    path = os.path.join(root, 'config.json')
    if not os.path.exists(path):
        path = os.path.join(root, 'config.example.json')
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    for platform in cfg['platforms'].values():
        for key in ('cli_db', 'tasks_index', 'home', 'data_dir'):
            if key in platform:
                platform[key] = os.path.expanduser(os.path.expandvars(platform[key]))
    if cfg['general'].get('backup_dir'):
        cfg['general']['backup_dir'] = os.path.expanduser(os.path.expandvars(cfg['general']['backup_dir']))
    return cfg


def load_summaries(path: str) -> dict:
    """摘要文件格式：{"platform": {sid: 摘要}} 或 {sid: 摘要}。"""
    if not path:
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out.update({sid: s for sid, s in v.items()})
        else:
            out[k] = v
    return out
