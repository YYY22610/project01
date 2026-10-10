"""导出 chat_messages 表为 Excel 文档（一次性工具，可重复运行）。"""
import asyncio
import json

import asyncpg
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

DSN = "postgresql://postgres:postgres@127.0.0.1:5432/travel_experiment"
OUT = r"D:\27475\WorkBuddy-搭建网站\chat_messages_export.xlsx"
CELL_LIMIT = 32000  # Excel 单单元格上限，超出截断避免写入报错


async def main():
    conn = await asyncpg.connect(DSN)
    rows = await conn.fetch(
        "SELECT id, user_id, agent_id, role, content, tool_calls, tool_call_id, created_at "
        "FROM chat_messages ORDER BY created_at ASC"
    )
    await conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "chat_messages"
    headers = ["id", "user_id", "agent_id", "role", "content",
               "tool_calls", "tool_call_id", "created_at"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        content = (r["content"] or "")
        if len(content) > CELL_LIMIT:
            content = content[:CELL_LIMIT] + " …[已截断]"
        tool_calls = r["tool_calls"]
        tc = json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else ""
        if len(tc) > CELL_LIMIT:
            tc = tc[:CELL_LIMIT] + " …[已截断]"
        ws.append([
            str(r["id"]),
            str(r["user_id"]),
            r["agent_id"],
            r["role"],
            content,
            tc,
            r["tool_call_id"] or "",
            r["created_at"].isoformat() if r["created_at"] else "",
        ])

    widths = [38, 38, 10, 10, 90, 45, 30, 22]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A2"
    wb.save(OUT)
    print(f"导出完成：{len(rows)} 行 -> {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
