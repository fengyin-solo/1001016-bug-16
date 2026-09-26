"""市民热线业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["记录编号", "来电人", "来电内容"]
OPTIONAL_FIELDS = ["问题位置", "问题类型"]
STATUS_ORDER = ["待转办", "已转办", "处理中", "已办结"]
# 动作 → 目标状态 / 需要填写的字段 / 允许执行的当前状态
ACTION_RULES: dict[str, dict[str, Any]] = {
    "转办部门": {"target": "已转办", "field": "转办部门", "from": ["待转办"]},
    "处理反馈": {"target": "处理中", "field": "处理结果", "from": ["已转办", "处理中"]},
    "办结归档": {"target": "已办结", "field": None, "from": ["处理中"]},
}
DONE_PHRASES = {"转办部门": "已转办", "处理反馈": "已填写处理结果", "办结归档": "已办结归档"}
NEGATIVE_ACTIONS = []


class ComplaintService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        caller: str | None = None,
        content: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("记录编号", ""))]
        if caller:
            rows = [row for row in rows if caller in str(row.get("来电人", ""))]
        if content:
            rows = [row for row in rows if content in str(row.get("来电内容", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def status_summary(self) -> dict[str, int]:
        """按状态统计热线记录量，给受理页的统计卡片用。"""
        summary = {status: 0 for status in STATUS_ORDER}
        for row in store.rows(MODULE):
            status = str(row.get("status") or "")
            if status in summary:
                summary[status] += 1
        return summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记热线记录；记录编号重复提交只生效一次，返回已受理的那条。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        code = str(values.get("记录编号") or "").strip()
        for row in store.rows(MODULE):
            if str(row.get("记录编号") or "").strip() == code:
                return row, [], True
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        entry["转办部门"] = ""
        entry["处理结果"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["记录状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], False

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"热线记录 {entry_id} 不存在或已归档"
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于市民热线可执行范围"
        target = str(rule["target"])
        field = rule["field"]
        current = str(entry.get("status") or "")
        code = entry.get("记录编号", entry_id)
        done = DONE_PHRASES[action]
        if current == target:
            # 同一动作重复提交只生效一次；字段值不同视为补充修改
            if field is None:
                return entry, f"热线记录{code}{done}，重复提交未重复处理"
            value = str(values.get(field) or "").strip()
            if not value or value == str(entry.get(field) or "").strip():
                return entry, f"热线记录{code}{done}，重复提交未重复处理"
            entry[field] = value
            return entry, f"热线记录{code}已更新{field}"
        if current not in rule["from"]:
            allowed = "、".join(rule["from"])
            return None, f"热线记录{code}当前状态为「{current}」，仅「{allowed}」状态可执行「{action}」"
        if field is not None:
            value = str(values.get(field) or "").strip()
            if not value:
                return None, f"{field}不能为空：请填写{field}后再提交"
            entry[field] = value
        if action == "办结归档" and not str(entry.get("处理结果") or "").strip():
            return None, f"热线记录{code}尚未填写处理结果，请先处理反馈再办结归档"
        entry["status"] = target
        entry["记录状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"热线记录{code}{done}"
