# -*- coding: utf-8 -*-
"""平台适配器基类。"""
from chatnamer.core import SessionInfo, PlanItem


class Adapter:
    """每个平台实现：discover（发现会话）、first_texts（取首条用户消息）、apply（写标题）。

    约定：
    - discover 只返回用户可见会话（排除各平台的子代理/内部会话），
      且已过滤标题符合格式与活跃窗口内的会话由 CLI 层处理。
    - apply 必须先备份目标库，再在单事务内写入，返回逐条结果。
    """
    name = 'base'

    def __init__(self, cfg: dict, root: str):
        self.cfg = cfg
        self.root = root
        self.pcfg = cfg['platforms'][self.name]

    def discover(self) -> list:
        raise NotImplementedError

    def first_texts(self, sids: list) -> dict:
        return {}

    def apply(self, items: list, backup_dir: str) -> list:
        raise NotImplementedError

    def notes(self) -> str:
        return ''
