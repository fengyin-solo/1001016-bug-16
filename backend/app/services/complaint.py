"""市民热线业务规则：状态流转、字段校验、幂等登记与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["记录编号", "来电人", "来电内容"]
STATUS_ORDER = ["待转办", "已转办", "处理中", "已办结"]
# 各动作对应的必填字段与流转到的目标状态。
ACTION_RULES = {
    "转办部门": {"target": "已转办", "required": "转办部门", "required_label": "转办部门"},
    "处理反馈": {"target": "处理中", "required": "处理结果", "required_label": "处理结论"},
    "办结归档": {"target": "已办结", "required": None, "required_label": ""},
}
NEGATIVE_ACTIONS: list[str] = []


def _status(row: dict[str, Any]) -> str:
    """以内部 status 为准，兼容历史数据里写成占位文本的「记录状态」。"""
    status = str(row.get("status") or "").strip()
    return status if status in STATUS_ORDER else STATUS_ORDER[0]


def _render(row: dict[str, Any]) -> dict[str, Any]:
    """列表、详情、弹窗共用同一份出参口径，保证三处看到的处理结论一致。"""
    rendered = dict(row)
    rendered["status"] = _status(row)
    rendered["记录状态"] = rendered["status"]
    rendered["处理结果"] = str(row.get("处理结果") or "").strip()
    return rendered


class ComplaintService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        caller: str | None = None,
        content: str | None = None,
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
            rows = [row for row in rows if _status(row) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_render(row) for row in rows[start:start + size]], total

    def stats(self) -> list[dict[str, Any]]:
        """受理页顶部的状态计数卡片。"""
        counts = {name: 0 for name in STATUS_ORDER}
        for row in store.rows(MODULE):
            counts[_status(row)] += 1
        return [
            {"label": "待转办记录", "value": counts["待转办"]},
            {"label": "处理中记录", "value": counts["处理中"]},
            {"label": "已办结记录", "value": counts["已办结"]},
        ]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _render(row) if row is not None else None

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记热线记录。

        返回 (记录, 缺失字段, 是否重复编号)：同一记录编号重复提交只保留首条，
        直接回传已有记录，不会再生成第二条。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        code = str(values.get("记录编号") or "").strip()
        rows = store.rows(MODULE)
        for row in rows:
            if str(row.get("记录编号") or "").strip() == code:
                return _render(row), [], True
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["记录编号", "来电人", "来电内容", "问题位置", "问题类型"]:
            entry[field] = str(values.get(field) or "").strip()
        entry["转办部门"] = str(values.get("转办部门") or "").strip()
        entry["处理结果"] = str(values.get("处理结果") or "").strip()
        entry["status"] = STATUS_ORDER[0]
        entry["记录状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _render(entry), [], False

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """执行转办/反馈/办结。

        返回 (记录, 说明, 是否真正发生状态变更)。已处于目标状态时按幂等处理：
        提示无需重复操作，但不会再次流转、也不会产生第二条记录。
        """
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"热线记录 {entry_id} 不存在或已归档", False
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于市民热线可执行范围", False
        current = _status(entry)
        current_idx = STATUS_ORDER.index(current)
        target = str(rule["target"])
        target_idx = STATUS_ORDER.index(target)
        if current_idx > target_idx:
            return None, f"记录当前为「{current}」，不能重复执行「{action}」", False
        if current_idx == target_idx:
            return _render(entry), f"热线记录已处于「{current}」，无需重复{action}", False
        required_field = rule["required"]
        if required_field is not None and not str(values.get(required_field) or "").strip():
            return None, f"{rule['required_label']}不能为空，请填写后再提交", False
        if required_field is not None:
            entry[required_field] = str(values.get(required_field) or "").strip()
        entry["status"] = target
        entry["记录状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _render(entry), f"热线记录已{action}", True
