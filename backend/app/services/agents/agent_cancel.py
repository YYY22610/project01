"""Agent 干预（取消）管理器。

按 (user_id, agent_id) 维度维护一个"请求取消"标志，用于在助理执行长耗时 /
有副作用操作（如发送邮件、生成 Word）时，让参与者随时中断当前轮次。

- 每一轮对话开始时调用 reset_cancel 清空标志。
- 参与者点击"停止"时调用 request_cancel 置位。
- base_agent 在关键节点调用 is_cancelled 检查，命中则立即终止本轮。
"""
from __future__ import annotations

import asyncio
from typing import Dict, Set


class AgentCancelManager:
    """进程内的取消标志表。key 为 f"{user_id}:{agent_id}"。"""

    def __init__(self) -> None:
        # 记录已请求取消的 key 集合
        self._flags: Set[str] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(user_id: str, agent_id: str) -> str:
        return f"{user_id}:{agent_id}"

    async def reset_cancel(self, user_id: str, agent_id: str) -> None:
        """新一轮对话开始：清空该 (用户, 助理) 的取消请求。"""
        async with self._lock:
            self._flags.discard(self._key(user_id, agent_id))

    async def request_cancel(self, user_id: str, agent_id: str) -> None:
        """参与者请求中断当前操作。"""
        async with self._lock:
            self._flags.add(self._key(user_id, agent_id))

    async def is_cancelled(self, user_id: str, agent_id: str) -> bool:
        """查询该 (用户, 助理) 是否已请求取消。"""
        async with self._lock:
            return self._key(user_id, agent_id) in self._flags


# 单例：整个进程共享
cancel_manager = AgentCancelManager()
