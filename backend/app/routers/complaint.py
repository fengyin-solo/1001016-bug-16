"""市民热线接口：维护热线记录，覆盖登记、转办部门、处理反馈、办结归档等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.complaint import STATUS_ORDER, ComplaintService

router = APIRouter(prefix="/api/complaint", tags=["市民热线"])

service = ComplaintService()

LIST_FIELDS = ["记录编号", "来电人", "来电内容", "问题位置", "问题类型", "转办部门", "处理结果", "记录状态"]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按记录编号检索"),
    caller: str | None = Query(default=None, description="按来电人检索"),
    content: str | None = Query(default=None, description="按来电内容检索"),
    status: str | None = Query(default=None, description="待转办、已转办、处理中、已办结"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按记录编号、来电人、来电内容与状态过滤市民热线列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status not in STATUS_ORDER:
        raise HTTPException(status_code=400, detail=f"状态「{status}」不在受理范围：{'、'.join(STATUS_ORDER)}")
    items, total = service.list_entries(
        keyword=keyword, caller=caller, content=content, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def entry_stats() -> dict[str, Any]:
    """受理页顶部卡片：各状态的热线记录数量。"""
    return {"items": service.stats()}


@router.get("/export")
def export_entries(
    status: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    """导出市民热线清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(keyword=keyword, status=status, page=1, size=10000)
    return {"module": "complaint", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条热线记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"热线记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult | JSONResponse:
    """登记一条热线记录。

    缺少必填字段（含来电内容为空）会明确说明原因，而不是静默退回；
    记录编号重复提交只生效一次，重复时回传已有记录。
    """
    entry, missing, duplicated = service.create_entry(payload.values)
    if missing:
        reason = "缺少必填字段：" + "、".join(missing)
        if "来电内容" in missing:
            reason += "；来电内容为空，无法说明市民诉求，请补充后再提交"
        return JSONResponse(status_code=400, content={"ok": False, "message": reason, "entry": None})
    if duplicated:
        return ActionResult(ok=True, duplicate=True, message="记录编号已存在，重复提交只生效一次，未再生成新记录", entry=entry)
    return ActionResult(ok=True, message="热线记录已登记，进入待转办队列", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult | JSONResponse:
    """对单条热线记录执行转办部门、处理反馈、办结归档；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, changed = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return JSONResponse(status_code=400, content={"ok": False, "message": message, "entry": None})
    return ActionResult(ok=True, changed=changed, message=message, entry=entry)
