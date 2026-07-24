"""
Lightweight Web-based Database Viewer for travel_experiment.
Run with: python db_viewer.py
Access at: http://localhost:8080
"""
import os
import asyncio
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Database config
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/travel_experiment")

engine = create_async_engine(DB_URL, echo=False)
app = FastAPI(title="DB Viewer")

# Tables to show
TABLES = [
    "users", "admin_users", "system_config", "questionnaire_items",
    "questionnaire_responses", "behavior_logs", "task_submissions",
    "chat_messages", "admin_scores", "reminders"
]

# Table descriptions
TABLE_INFO = {
    "users": "参与者用户表",
    "admin_users": "管理员账号表",
    "system_config": "系统配置表",
    "questionnaire_items": "问卷题项表",
    "questionnaire_responses": "问卷回答表",
    "behavior_logs": "行为日志表",
    "task_submissions": "任务提交表",
    "chat_messages": "AI对话记录表",
    "admin_scores": "评分记录表",
    "reminders": "提醒事项表",
}


@app.get("/", response_class=HTMLResponse)
async def index():
    """Dashboard: show table list with row counts."""
    counts = {}
    for t in TABLES:
        async with engine.connect() as conn:
            result = await conn.execute(text(f'SELECT count(*) FROM "{t}"'))
            counts[t] = result.scalar()

    cards = ""
    for t in TABLES:
        cnt = counts.get(t, 0)
        color = "#3b82f6" if cnt > 0 else "#6b7280"
        cards += f"""
        <div class="card" onclick="location.href='/table/{t}'">
            <div class="card-header">
                <span class="table-name">{t}</span>
                <span class="table-desc">{TABLE_INFO.get(t, '')}</span>
            </div>
            <div class="card-count" style="color:{color}">{cnt}</div>
            <div class="card-label">rows</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Database Viewer - travel_experiment</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #1f2937; }}
    .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: white; padding: 24px 32px; }}
    .header h1 {{ font-size: 24px; font-weight: 600; }}
    .header .subtitle {{ font-size: 14px; opacity: 0.8; margin-top: 4px; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }}
    .card {{ background: white; border-radius: 12px; padding: 20px; cursor: pointer; transition: all 0.2s; border: 1px solid #e5e7eb; }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); border-color: #3b82f6; }}
    .card-header {{ margin-bottom: 12px; }}
    .table-name {{ font-size: 15px; font-weight: 600; color: #1f2937; display: block; }}
    .table-desc {{ font-size: 12px; color: #9ca3af; }}
    .card-count {{ font-size: 32px; font-weight: 700; }}
    .card-label {{ font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; }}
    .sql-section {{ margin-top: 32px; background: white; border-radius: 12px; padding: 24px; border: 1px solid #e5e7eb; }}
    .sql-section h2 {{ font-size: 18px; margin-bottom: 16px; }}
    textarea {{ width: 100%; height: 80px; border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; font-family: 'Courier New', monospace; font-size: 14px; resize: vertical; }}
    .btn {{ display: inline-block; background: #2563eb; color: white; border: none; padding: 10px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; margin-top: 8px; }}
    .btn:hover {{ background: #1d4ed8; }}
    .footer {{ text-align: center; padding: 24px; color: #9ca3af; font-size: 13px; }}
</style>
</head>
<body>
    <div class="header">
        <h1>Database Viewer</h1>
        <div class="subtitle">travel_experiment &middot; PostgreSQL 17.10 &middot; 10 tables</div>
    </div>
    <div class="container">
        <div class="grid">{cards}</div>
        <div class="sql-section">
            <h2>SQL Query</h2>
            <form method="get" action="/sql">
                <textarea name="q" placeholder="SELECT * FROM users LIMIT 10;">SELECT * FROM users LIMIT 10;</textarea>
                <br>
                <button type="submit" class="btn">Execute</button>
            </form>
        </div>
    </div>
    <div class="footer">Powered by FastAPI + asyncpg &middot; Click any table card to view data</div>
</body>
</html>"""


@app.get("/table/{table_name}", response_class=HTMLResponse)
async def view_table(table_name: str, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500)):
    """View table data with pagination."""
    if table_name not in TABLES:
        return HTMLResponse("<h2>Invalid table name</h2>", status_code=400)

    offset = (page - 1) * size

    async with engine.connect() as conn:
        # Get total count
        count_result = await conn.execute(text(f'SELECT count(*) FROM "{table_name}"'))
        total = count_result.scalar()

        # Get column names
        col_result = await conn.execute(text(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        columns = col_result.fetchall()

        # Get data
        data_result = await conn.execute(text(f"""
            SELECT * FROM "{table_name}"
            ORDER BY 1
            LIMIT {size} OFFSET {offset}
        """))
        rows = data_result.fetchall()
        col_keys = data_result.keys()

    # Build table HTML
    header_cells = "".join(f"<th>{c}</th>" for c in col_keys)
    body_rows = ""
    for row in rows:
        cells = ""
        for val in row:
            if val is None:
                cells += '<td class="null">NULL</td>'
            elif isinstance(val, str) and len(val) > 100:
                cells += f'<td title="{val}">{val[:100]}...</td>'
            else:
                cells += f"<td>{val}</td>"
        body_rows += f"<tr>{cells}</tr>"

    # Pagination
    total_pages = max(1, (total + size - 1) // size)
    prev_page = f'<a href="/table/{table_name}?page={page-1}&size={size}" class="page-btn">&laquo; Prev</a>' if page > 1 else '<span class="page-btn disabled">&laquo; Prev</span>'
    next_page = f'<a href="/table/{table_name}?page={page+1}&size={size}" class="page-btn">Next &raquo;</a>' if page < total_pages else '<span class="page-btn disabled">Next &raquo;</span>'

    page_info = f"Page {page} / {total_pages} &middot; {total} total rows"

    # Column info
    col_info_rows = ""
    for col in columns:
        nullable_color = "#ef4444" if col[2] == "NO" else "#9ca3af"
        col_info_rows += f"<tr><td><code>{col[0]}</code></td><td>{col[1]}</td><td style='color:{nullable_color}'>{col[2]}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{table_name} - DB Viewer</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #1f2937; }}
    .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: white; padding: 20px 32px; }}
    .header h1 {{ font-size: 22px; }}
    .header .nav {{ font-size: 13px; opacity: 0.8; margin-top: 4px; }}
    .header .nav a {{ color: #bfdbfe; text-decoration: none; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    .toolbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }}
    .toolbar .info {{ font-size: 14px; color: #6b7280; }}
    .pagination {{ display: flex; gap: 8px; align-items: center; }}
    .page-btn {{ display: inline-block; padding: 8px 16px; background: white; border: 1px solid #d1d5db; border-radius: 8px; text-decoration: none; color: #374151; font-size: 14px; transition: all 0.15s; }}
    .page-btn:hover:not(.disabled) {{ background: #eff6ff; border-color: #3b82f6; color: #2563eb; }}
    .page-btn.disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .table-wrap {{ overflow-x: auto; background: white; border-radius: 12px; border: 1px solid #e5e7eb; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    thead th {{ background: #f9fafb; padding: 12px 16px; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; white-space: nowrap; }}
    tbody td {{ padding: 10px 16px; border-bottom: 1px solid #f3f4f6; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    tbody tr:hover {{ background: #f9fafb; }}
    td.null {{ color: #d1d5db; font-style: italic; }}
    .schema-section {{ margin-top: 32px; }}
    .schema-section h2 {{ font-size: 18px; margin-bottom: 12px; }}
    .schema-table {{ background: white; border-radius: 12px; border: 1px solid #e5e7eb; overflow: hidden; }}
    .size-select {{ padding: 6px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; }}
</style>
</head>
<body>
    <div class="header">
        <h1>📋 {table_name}</h1>
        <div class="nav"><a href="/">&larr; Back to Dashboard</a> &middot; {TABLE_INFO.get(table_name, '')}</div>
    </div>
    <div class="container">
        <div class="toolbar">
            <div class="info">{page_info}</div>
            <div class="pagination">
                <select class="size-select" onchange="location.href='/table/{table_name}?page=1&size='+this.value">
                    <option value="50" {'selected' if size==50 else ''}>50 / page</option>
                    <option value="100" {'selected' if size==100 else ''}>100 / page</option>
                    <option value="200" {'selected' if size==200 else ''}>200 / page</option>
                </select>
                {prev_page}
                {next_page}
            </div>
        </div>
        <div class="table-wrap">
            <table>
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{body_rows if body_rows else '<tr><td colspan="100" style="text-align:center;padding:40px;color:#9ca3af;">No data in this table</td></tr>'}</tbody>
            </table>
        </div>
        <div class="schema-section">
            <h2>Column Schema</h2>
            <div class="schema-table">
                <table>
                    <thead><tr><th>Column</th><th>Type</th><th>Nullable</th></tr></thead>
                    <tbody>{col_info_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""


@app.get("/sql", response_class=HTMLResponse)
async def run_sql(q: str = Query("SELECT * FROM users LIMIT 10;")):
    """Execute a read-only SQL query and display results."""
    # Safety: only allow SELECT
    q_stripped = q.strip()
    if not q_stripped.upper().startswith("SELECT"):
        return HTMLResponse("<h2 style='color:red;padding:24px;'>Only SELECT queries are allowed.</h2>", status_code=400)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(q))
            rows = result.fetchall()
            col_keys = result.keys()
    except Exception as e:
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
        body {{ font-family: sans-serif; padding: 40px; }}
        .error {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; color: #991b1b; }}
        pre {{ white-space: pre-wrap; margin-top: 8px; }}
        a {{ color: #2563eb; }}
        </style></head><body>
        <div class="error"><h3>SQL Error</h3><pre>{str(e)}</pre></div>
        <p style="margin-top:16px;"><a href="/">&larr; Back to Dashboard</a></p>
        </body></html>"""

    header_cells = "".join(f"<th>{c}</th>" for c in col_keys)
    body_rows = ""
    for row in rows:
        cells = ""
        for val in row:
            if val is None:
                cells += '<td class="null">NULL</td>'
            elif isinstance(val, str) and len(val) > 200:
                cells += f'<td title="{val}">{val[:200]}...</td>'
            else:
                cells += f"<td>{val}</td>"
        body_rows += f"<tr>{cells}</tr>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SQL Result - DB Viewer</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #1f2937; }}
    .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); color: white; padding: 20px 32px; }}
    .header h1 {{ font-size: 22px; }}
    .header .nav a {{ color: #bfdbfe; text-decoration: none; font-size: 13px; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    .query-box {{ background: #1e293b; color: #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; font-family: 'Courier New', monospace; font-size: 14px; white-space: pre-wrap; }}
    .info {{ font-size: 14px; color: #6b7280; margin-bottom: 12px; }}
    .table-wrap {{ overflow-x: auto; background: white; border-radius: 12px; border: 1px solid #e5e7eb; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    thead th {{ background: #f9fafb; padding: 12px 16px; text-align: left; font-weight: 600; border-bottom: 2px solid #e5e7eb; white-space: nowrap; }}
    tbody td {{ padding: 10px 16px; border-bottom: 1px solid #f3f4f6; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    tbody tr:hover {{ background: #f9fafb; }}
    td.null {{ color: #d1d5db; font-style: italic; }}
</style>
</head>
<body>
    <div class="header">
        <h1>SQL Query Result</h1>
        <div class="nav"><a href="/">&larr; Back to Dashboard</a></div>
    </div>
    <div class="container">
        <div class="query-box">{q}</div>
        <div class="info">{len(rows)} rows returned</div>
        <div class="table-wrap">
            <table>
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{body_rows if body_rows else '<tr><td colspan="100" style="text-align:center;padding:40px;color:#9ca3af;">No rows returned</td></tr>'}</tbody>
            </table>
        </div>
    </div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Database Viewer")
    print("  http://localhost:8080")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080)
