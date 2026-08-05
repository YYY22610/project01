"""Quick functional test for admin questionnaire CRUD endpoints.

Runs in-process against the FastAPI app (no need for a running uvicorn).
Requires the backend venv and Postgres to be up.
"""
import asyncio
import os
import sys

# Force mock LLM so import does not need a real key
os.environ.setdefault("LLM_API_KEY", "")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from app.main import app
from app.database import engine


async def run():
    from app.models.admin_user import AdminUser
    from app.services.auth_service import hash_password, create_admin_token
    from app.database import async_session_factory

    # Ensure admin exists
    async with async_session_factory() as db:
        from sqlalchemy import select
        admin = (await db.execute(select(AdminUser).where(AdminUser.username == "admin"))).scalar_one_or_none()
        if not admin:
            admin = AdminUser(username="admin", password_hash=hash_password("admin123"))
            db.add(admin)
            await db.commit()

    token = create_admin_token("admin")
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create
        create_res = await client.post("/api/admin/questionnaire-config", json={
            "construct": "usefulness",
            "text": "test01",
            "type": "likert5",
            "options": None,
        }, headers=headers)
        assert create_res.status_code == 200, f"Create failed: {create_res.status_code} {create_res.text}"
        created = create_res.json()
        item_id = created["id"]
        assert created["text"] == "test01"
        assert created["type"] == "likert5"
        print(f"[OK] CREATE id={item_id}")

        # 2. List
        list_res = await client.get("/api/admin/questionnaire-config", headers=headers)
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(i["id"] == item_id for i in items)
        print(f"[OK] LIST found {len(items)} items")

        # 3. Update
        update_res = await client.put(f"/api/admin/questionnaire-config/{item_id}", json={
            "construct": "trust",
            "text": "test01 updated",
            "type": "likert7",
        }, headers=headers)
        assert update_res.status_code == 200, f"Update failed: {update_res.status_code} {update_res.text}"
        updated = update_res.json()
        assert updated["construct"] == "trust"
        assert updated["text"] == "test01 updated"
        assert updated["type"] == "likert7"
        assert updated["scale_level"] == 7
        print("[OK] UPDATE")

        # 4. Update to choice with options
        update2_res = await client.put(f"/api/admin/questionnaire-config/{item_id}", json={
            "type": "single_choice",
            "options": ["A", "B", "C"],
        }, headers=headers)
        assert update2_res.status_code == 200, f"Update2 failed: {update2_res.status_code} {update2_res.text}"
        updated2 = update2_res.json()
        assert updated2["type"] == "single_choice"
        assert updated2["options"] == ["A", "B", "C"]
        print("[OK] UPDATE to choice")

        # 5. Delete
        del_res = await client.delete(f"/api/admin/questionnaire-config/{item_id}", headers=headers)
        assert del_res.status_code == 200, f"Delete failed: {del_res.status_code} {del_res.text}"
        print("[OK] DELETE")

        # 6. Verify deleted
        list2_res = await client.get("/api/admin/questionnaire-config", headers=headers)
        assert not any(i["id"] == item_id for i in list2_res.json())
        print("[OK] item removed from list")

    print("\nAll questionnaire admin CRUD checks passed.")


async def run_all():
    try:
        await run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_all())
