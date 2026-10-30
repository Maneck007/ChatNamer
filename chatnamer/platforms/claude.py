# -*- coding: utf-8 -*-
"""Claude 适配器（占位）。

Claude 桌面客户端的对话存储在云端（claude.ai 账号），本地
%LOCALAPPDATA%\\Claude-Data 下的 IndexedDB 只是网页缓存，改本地不会同步回
服务器。因此当前版本不做任何改名，只输出说明；如未来接入官方接口，
在 apply/discover 中实现即可。
"""
from chatnamer.platforms.base import Adapter as BaseAdapter


class Adapter(BaseAdapter):
    name = 'claude'

    def discover(self):
        return []

    def apply(self, items, backup_dir):
        return []

    def notes(self):
        return ('Claude 对话在云端（claude.ai），本地仅缓存，无法本地改名。'
                '请在 Claude 客户端中手动重命名需要整理的对话；'
                '后续如需自动化，可评估 claude.ai 官方/内部接口方案。')
