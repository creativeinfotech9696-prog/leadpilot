import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Literal, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import BulkWriteError
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

try:  # launched as `backend.server` (the default)
    from backend.clerk_auth import clerk_router, require_user
    from backend import ai, analytics, demo, ingest
except ModuleNotFoundError:  # launched from inside backend/ as `server`
    from clerk_auth import clerk_router, require_user
    import ai
    import analytics
    import demo
    import ingest

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
logger = logging.getLogger(__name__)

INDEXES: dict[str, list[IndexModel]] = {
    "calls": [
        IndexModel([("key", ASCENDING)], name="key", unique=True),
        IndexModel([("ts", DESCENDING)], name="ts_desc"),
        IndexModel([("upload_id", ASCENDING)], name="upload_id"),
        IndexModel([("list", ASCENDING), ("ts", DESCENDING)], name="list_ts"),
        IndexModel([("cli", ASCENDING), ("ts", DESCENDING)], name="cli_ts"),
        IndexModel([("cli_upload_id", ASCENDING)], name="cli_upload_id"),
    ],
    "cdr": [
        IndexModel([("key", ASCENDING)], name="key", unique=True),
        IndexModel([("ts", ASCENDING)], name="ts"),
        IndexModel([("upload_id", ASCENDING)], name="upload_id"),
    ],
    "uploads": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "recommendations": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")],
    "memory": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "chat_messages": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")],
    "mappings": [IndexModel([("signature", ASCENDING)], name="signature", unique=True)],
    "settings": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)

app = FastAPI()
api_router = APIRouter(prefix="/api")

DEFAULT_SETTINGS = {"id": "workspace", "timezone": "America/New_York", "disposition_map": {}, "min_dials": 100,
                    "cli_drop_pct": 35, "list_drop_pct": 30, "list_costs": {}, "cdr_match_seconds": 120}
STATE = {"version": 0, "cache": {}, "ai": {"running": False, "last_run": None, "last_error": None}, "task": None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bump() -> None:
    STATE["version"] += 1
    STATE["cache"].clear()


async def get_settings() -> dict:
    s = await db.settings.find_one({"id": "workspace"}, {"_id": 0})
    return {**DEFAULT_SETTINGS, **(s or {})}


async def get_analysis(days: int) -> dict:
    key = (STATE["version"], days)
    if key not in STATE["cache"]:
        s = await get_settings()
        df, anchor = await analytics.load_df(db, days)
        res = await asyncio.to_thread(analytics.analyze, df, s, anchor, days)
        res["demo_active"] = bool(await db.uploads.find_one({"is_demo": True}, {"_id": 1}))
        STATE["cache"][key] = res
    return STATE["cache"][key]


async def ai_context(analysis: dict) -> str:
    s = await get_settings()
    memory = await db.memory.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(80)
    feedback = await db.recommendations.find({"status": {"$in": ["applied", "ignored", "failed"]}}, {"_id": 0}).sort("feedback_at", -1).to_list(40)
    return ai.build_context(analysis, s, memory, feedback)


async def add_memory(type_: str, text: str, source: str) -> dict:
    doc = {"id": str(uuid.uuid4()), "type": type_, "text": text.strip(), "source": source, "active": True,
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.memory.insert_one(dict(doc))
    return doc


# ---------- analytics ----------
@api_router.get("/")
async def root():
    return {"message": "Dialer Intelligence API"}


@api_router.get("/analytics")
async def analytics_route(days: int = Query(14, ge=0, le=365), user: dict = Depends(require_user)):
    return await get_analysis(days)


# ---------- uploads ----------
async def read_upload(file: UploadFile):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls", ".txt"):
        raise HTTPException(400, "Please upload a CSV or Excel file")
    data = await file.read()
    try:
        return await asyncio.to_thread(ingest.read_bytes, data, ext)
    except Exception:
        raise HTTPException(400, "Could not read this file. Export it again from Primo as CSV or Excel.")


async def disp_rows(df, column):
    s = await get_settings()
    return [{**d, "category": s["disposition_map"].get(d["name"]) or analytics.guess_category(d["name"])}
            for d in ingest.disposition_counts(df, column)]


def sig(kind: str, cols: list) -> str:
    return f"{kind}:{ingest.signature(cols)}"


@api_router.post("/uploads/preview")
async def upload_preview(file: UploadFile = File(...), kind: Literal["calls", "cdr"] = Form("calls"), user: dict = Depends(require_user)):
    df = await read_upload(file)
    cols = list(df.columns)
    saved = await db.mappings.find_one({"signature": sig(kind, cols)}, {"_id": 0})
    mapping = {**ingest.suggest(cols, kind), **(saved["mapping"] if saved else {})}
    s = await get_settings()
    return {"kind": kind, "filename": file.filename, "rows": len(df), "columns": cols, "mapping": mapping,
            "known_format": bool(saved), "sample": df.head(5).to_dict("records"),
            "file_tz": (saved or {}).get("file_tz") or s["timezone"],
            "dispositions": await disp_rows(df, mapping.get("disposition")) if kind == "calls" else []}


@api_router.post("/uploads/dispositions")
async def upload_dispositions(file: UploadFile = File(...), column: str = Form(...), user: dict = Depends(require_user)):
    return await disp_rows(await read_upload(file), column)


class CommitIn(BaseModel):
    kind: Literal["calls", "cdr"] = "calls"
    file_tz: Optional[str] = None
    mapping: Dict[str, Optional[str]]
    disposition_map: Dict[str, Literal["sale", "contact", "connected", "none"]] = {}


async def insert_calls(docs: list, coll: str = "calls") -> int:
    n = 0
    for i in range(0, len(docs), 5000):
        try:
            r = await db[coll].insert_many(docs[i:i + 5000], ordered=False)
            n += len(r.inserted_ids)
        except BulkWriteError as e:
            n += e.details.get("nInserted", 0)
    return n


async def run_cli_match() -> int:
    s = await get_settings()
    calls = await db.calls.find({"cli": "Unknown"}, {"_id": 1, "phone": 1, "ts": 1, "direction": 1, "call_id": 1}).to_list(None)
    if not calls:
        return 0
    df = pd.DataFrame(calls)
    lo, hi = df["ts"].min() - timedelta(hours=2), df["ts"].max() + timedelta(hours=2)
    cdr = await db.cdr.find({"ts": {"$gte": lo, "$lte": hi}}, {"_id": 0, "from": 1, "to": 1, "ts": 1, "call_id": 1, "upload_id": 1}).to_list(None)
    if not cdr:
        return 0
    res = await asyncio.to_thread(ingest.match_cli, df, pd.DataFrame(cdr), s["cdr_match_seconds"])
    for (cli, up), g in res.groupby(["cli", "upload_id"]):
        await db.calls.update_many({"_id": {"$in": list(g["_id"])}}, {"$set": {"cli": cli, "cli_upload_id": up}})
    return len(res)


async def reset_cdr_clis(flt: dict) -> None:
    await db.calls.update_many({"cli_upload_id": {"$exists": True}, **flt}, {"$set": {"cli": "Unknown"}, "$unset": {"cli_upload_id": ""}})


async def finish_ingest(upload: dict, disposition_map: dict) -> dict:
    upload["cli_matched"] = await run_cli_match()
    await db.uploads.insert_one(dict(upload))
    if disposition_map:
        s = await get_settings()
        dm = {**s["disposition_map"], **{k.upper().strip(): v for k, v in disposition_map.items()}}
        await db.settings.update_one({"id": "workspace"}, {"$set": {"disposition_map": dm}}, upsert=True)
    bump()
    await evaluate_outcomes()
    start_generation()
    return upload


@api_router.post("/uploads/commit")
async def upload_commit(file: UploadFile = File(...), payload: str = Form(...), user: dict = Depends(require_user)):
    try:
        body = CommitIn.model_validate_json(payload)
    except Exception:
        raise HTTPException(400, "Invalid column mapping")
    cdr = body.kind == "cdr"
    missing = [f for f in (ingest.CDR_REQUIRED if cdr else ingest.REQUIRED) if not body.mapping.get(f)]
    if missing:
        raise HTTPException(400, f"Please map these columns: {', '.join(missing)}")
    s = await get_settings()
    tz = body.file_tz or s["timezone"]
    try:
        ZoneInfo(tz)
    except Exception:
        raise HTTPException(400, "Unknown time zone")
    upload_id = str(uuid.uuid4())
    df = await read_upload(file)
    build = ingest.build_cdr_docs if cdr else ingest.build_docs
    docs, invalid = await asyncio.to_thread(build, df, body.mapping, tz, upload_id)
    if not docs:
        raise HTTPException(400, "No rows had a readable date/time. Check the timestamp column mapping.")
    inserted = await insert_calls(docs, "cdr" if cdr else "calls")
    await db.mappings.update_one({"signature": sig(body.kind, list(df.columns))},
                                 {"$set": {"mapping": body.mapping, "file_tz": tz, "updated_at": now_iso()}}, upsert=True)
    upload = {"id": upload_id, "kind": body.kind, "filename": file.filename, "rows_total": len(df), "rows_imported": inserted,
              "duplicates": len(docs) - inserted, "invalid": invalid, "is_demo": False, "file_tz": tz,
              "date_from": min(d["ts"] for d in docs).isoformat(), "date_to": max(d["ts"] for d in docs).isoformat(),
              "lists": 0 if cdr else len({d["list"] for d in docs}),
              "clis": len({d["from"] for d in docs}) if cdr else len({d["cli"] for d in docs} - {"Unknown"}),
              "created_at": now_iso(), "uploaded_by": user["user_id"]}
    return await finish_ingest(upload, {} if cdr else body.disposition_map)


@api_router.post("/demo/load")
async def demo_load(user: dict = Depends(require_user)):
    for u in await db.uploads.find({"is_demo": True}, {"_id": 0, "id": 1}).to_list(10):
        await db.calls.delete_many({"upload_id": u["id"]})
    await db.uploads.delete_many({"is_demo": True})
    upload_id = str(uuid.uuid4())
    docs = await asyncio.to_thread(demo.generate, upload_id)
    inserted = await insert_calls(docs)
    upload = {"id": upload_id, "kind": "calls", "filename": "Sample Primo data (demo)", "rows_total": len(docs), "rows_imported": inserted,
              "duplicates": 0, "invalid": 0, "is_demo": True, "date_from": min(d["ts"] for d in docs).isoformat(),
              "date_to": max(d["ts"] for d in docs).isoformat(), "lists": len(demo.LISTS), "clis": len(demo.CLIS),
              "created_at": now_iso(), "uploaded_by": user["user_id"]}
    return await finish_ingest(upload, {})


@api_router.get("/uploads")
async def list_uploads(user: dict = Depends(require_user)):
    return await db.uploads.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.delete("/uploads/{upload_id}")
async def delete_upload(upload_id: str, user: dict = Depends(require_user)):
    if (await db.uploads.delete_one({"id": upload_id})).deleted_count == 0:
        raise HTTPException(404, "Not found")
    await db.calls.delete_many({"upload_id": upload_id})
    await db.cdr.delete_many({"upload_id": upload_id})
    await reset_cdr_clis({"cli_upload_id": upload_id})
    await run_cli_match()
    bump()
    await db.recommendations.update_many({"status": "new"}, {"$set": {"status": "stale"}})
    if await db.calls.find_one({}, {"_id": 1}):
        start_generation()
    return {"ok": True}


# ---------- settings ----------
class SettingsIn(BaseModel):
    timezone: str
    min_dials: int = Field(ge=10, le=100000)
    cli_drop_pct: float = Field(ge=5, le=95)
    list_drop_pct: float = Field(ge=5, le=95)
    disposition_map: Dict[str, Literal["sale", "contact", "connected", "none"]] = {}
    list_costs: Dict[str, float] = {}
    cdr_match_seconds: int = Field(default=120, ge=10, le=1800)


@api_router.post("/cdr/rematch")
async def cdr_rematch(user: dict = Depends(require_user)):
    await reset_cdr_clis({})
    matched = await run_cli_match()
    bump()
    start_generation()
    return {"matched": matched}


@api_router.get("/settings")
async def get_settings_route(user: dict = Depends(require_user)):
    s = await get_settings()
    rows = await db.calls.aggregate([{"$group": {"_id": "$disposition", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]).to_list(300)
    s["dispositions"] = [{"name": r["_id"], "count": r["count"],
                          "category": s["disposition_map"].get(r["_id"]) or analytics.guess_category(r["_id"])} for r in rows]
    s["lists"] = sorted(await db.calls.distinct("list"))
    s["cdr_rows"] = await db.cdr.estimated_document_count()
    return s


@api_router.put("/settings")
async def put_settings(body: SettingsIn, user: dict = Depends(require_user)):
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(400, "Unknown time zone")
    data = body.model_dump()
    data["disposition_map"] = {k.upper().strip(): v for k, v in data["disposition_map"].items()}
    data["list_costs"] = {k: v for k, v in data["list_costs"].items() if v and v > 0}
    old = await get_settings()
    await db.settings.update_one({"id": "workspace"}, {"$set": data}, upsert=True)
    if old["cdr_match_seconds"] != data["cdr_match_seconds"]:
        await reset_cdr_clis({})
        await run_cli_match()
    bump()
    return await get_settings()


# ---------- recommendations ----------
def target_metrics(analysis: dict, rtype: str, target: str) -> Optional[dict]:
    rows = analysis.get("lists" if rtype == "list" else "clis", []) if rtype in ("list", "cli") else []
    hit = next((r for r in rows if r.get(rtype) == target), None)
    return {k: hit[k] for k in ("dials", "connect_rate", "conv_rate")} if hit else None


async def run_generation() -> None:
    st = STATE["ai"]
    if st["running"]:
        return
    st["running"], st["last_error"] = True, None
    try:
        analysis = await get_analysis(14)
        if not analysis.get("has_data"):
            return
        ctx = await ai_context(analysis)
        recs = await ai.generate_recommendations(f"recs-{uuid.uuid4().hex}", ctx)
        await db.recommendations.update_many({"status": "new"}, {"$set": {"status": "stale"}})
        batch = str(uuid.uuid4())
        docs = [{**r, "id": str(uuid.uuid4()), "batch_id": batch, "status": "new", "created_at": now_iso(),
                 "feedback_note": "", "feedback_at": None, "applied_at": None, "outcome": None,
                 "baseline": {"overall": {k: analysis["kpis"][k] for k in ("dials", "connect_rate", "conv_rate")},
                              "target": target_metrics(analysis, r["target_type"], r["target"])}} for r in recs]
        if docs:
            await db.recommendations.insert_many([dict(d) for d in docs])
        st["last_run"] = now_iso()
    except Exception as e:
        logger.exception("recommendation generation failed")
        st["last_error"] = str(e)[:300]
    finally:
        st["running"] = False


def start_generation() -> None:
    if not STATE["ai"]["running"]:
        STATE["task"] = asyncio.create_task(run_generation())


async def evaluate_outcomes() -> None:
    s = await get_settings()
    for r in await db.recommendations.find({"status": "applied", "outcome": None}, {"_id": 0}).to_list(200):
        applied = datetime.fromisoformat(r["applied_at"]).astimezone(timezone.utc).replace(tzinfo=None)
        flt = {r["target_type"]: r["target"]} if r["target_type"] in ("list", "cli") and r["target"] else {}
        proj = analytics.PROJ
        after = await db.calls.find({**flt, "ts": {"$gte": applied}}, proj).to_list(200000)
        if flt and len(after) < s["min_dials"] // 2:  # target paused/rested: judge by the whole floor
            flt = {}
            after = await db.calls.find({"ts": {"$gte": applied}}, proj).to_list(200000)
        before = await db.calls.find({**flt, "ts": {"$gte": applied - timedelta(days=7), "$lt": applied}}, proj).to_list(200000)
        if not after or not before:
            continue
        res = await asyncio.to_thread(analytics.compare, pd.DataFrame(before), pd.DataFrame(after), s)
        if not res:
            continue
        res["scope"] = r["target"] if flt else "all calls"
        res["evaluated_at"] = now_iso()
        await db.recommendations.update_one({"id": r["id"]}, {"$set": {"outcome": res}})
        word = {"worked": "WORKED", "worse": "MADE THINGS WORSE", "no_change": "had no clear effect"}[res["verdict"]]
        b, a = res["before"], res["after"]
        await add_memory("learned", f"[{r['category']}] '{r['title']}' {word} on {res['scope']}: connect {b['connect_rate']}% -> "
                                    f"{a['connect_rate']}%, conversion {b['conv_rate']}% -> {a['conv_rate']}%.", "outcome")


@api_router.get("/recommendations")
async def list_recs(status: str = "active", user: dict = Depends(require_user)):
    q = {"status": "new"} if status == "active" else {} if status == "all" else {"status": status}
    if status == "all":
        q = {"status": {"$ne": "stale"}}
    return await db.recommendations.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.get("/recommendations/status")
async def recs_status(user: dict = Depends(require_user)):
    return {k: STATE["ai"][k] for k in ("running", "last_run", "last_error")}


@api_router.post("/recommendations/generate")
async def recs_generate(user: dict = Depends(require_user)):
    if not await db.calls.find_one({}, {"_id": 1}):
        raise HTTPException(400, "Upload a dialer report first")
    start_generation()
    return {"started": True}


class FeedbackIn(BaseModel):
    status: Literal["applied", "ignored", "failed", "new"]
    note: str = ""


@api_router.patch("/recommendations/{rec_id}")
async def recs_feedback(rec_id: str, body: FeedbackIn, user: dict = Depends(require_user)):
    rec = await db.recommendations.find_one({"id": rec_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Not found")
    upd = {"status": body.status, "feedback_note": body.note.strip(), "feedback_at": now_iso(),
           "applied_at": now_iso() if body.status == "applied" else None, "outcome": None, "memory_id": None}
    if rec.get("memory_id"):
        await db.memory.delete_one({"id": rec["memory_id"]})
    mem = None
    if body.status == "failed":
        mem = await add_memory("learned", f"[{rec['category']}] '{rec['title']}' did NOT work in practice"
                                          + (f": {body.note.strip()}" if body.note.strip() else "."), "feedback")
    elif body.status == "ignored" and body.note.strip():
        mem = await add_memory("note", f"Operator skipped '{rec['title']}': {body.note.strip()}", "feedback")
    if mem:
        upd["memory_id"] = mem["id"]
    await db.recommendations.update_one({"id": rec_id}, {"$set": upd})
    return {**rec, **upd}


# ---------- memory ----------
class MemoryIn(BaseModel):
    type: Literal["rule", "note", "learned"]
    text: str = Field(min_length=2, max_length=1000)


class MemoryPatch(BaseModel):
    text: Optional[str] = Field(default=None, min_length=2, max_length=1000)
    active: Optional[bool] = None


@api_router.get("/memory")
async def list_memory(user: dict = Depends(require_user)):
    return await db.memory.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.post("/memory")
async def create_memory(body: MemoryIn, user: dict = Depends(require_user)):
    return await add_memory(body.type, body.text, "operator")


@api_router.patch("/memory/{mem_id}")
async def patch_memory(mem_id: str, body: MemoryPatch, user: dict = Depends(require_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    upd["updated_at"] = now_iso()
    if (await db.memory.update_one({"id": mem_id}, {"$set": upd})).matched_count == 0:
        raise HTTPException(404, "Not found")
    return await db.memory.find_one({"id": mem_id}, {"_id": 0})


@api_router.delete("/memory/{mem_id}")
async def delete_memory(mem_id: str, user: dict = Depends(require_user)):
    if (await db.memory.delete_one({"id": mem_id})).deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------- chat ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@api_router.get("/chat/messages")
async def chat_messages(user: dict = Depends(require_user)):
    msgs = await db.chat_messages.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return msgs[::-1]


@api_router.delete("/chat/messages")
async def clear_chat(user: dict = Depends(require_user)):
    await db.chat_messages.delete_many({"user_id": user["user_id"]})
    return {"ok": True}


@api_router.post("/chat/stream")
async def chat_stream(body: ChatIn, user: dict = Depends(require_user)):
    uid = user["user_id"]
    history = (await db.chat_messages.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(12))[::-1]
    await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "user_id": uid, "role": "user", "content": body.message, "created_at": now_iso()})
    ctx = await ai_context(await get_analysis(14))

    async def gen():
        full = ""
        try:
            async for delta in ai.stream(f"chat-{uid}-{uuid.uuid4().hex}", ai.chat_system(ctx), ai.chat_prompt(history, body.message)):
                full += delta
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception as e:
            logger.exception("chat failed")
            yield f"data: {json.dumps({'error': 'The AI assistant is unavailable right now. Please try again.'})}\n\n"
            if not full:
                return
        saved = []
        for rule in re.findall(r"^\s*\**REMEMBER:\**\s*(.+)$", full, re.M):
            saved.append(await add_memory("rule", rule.strip(), "chat"))
        await db.chat_messages.insert_one({"id": str(uuid.uuid4()), "user_id": uid, "role": "assistant", "content": full, "created_at": now_iso()})
        yield f"data: {json.dumps({'done': True, 'memory_saved': [m['text'] for m in saved]})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(api_router)
app.include_router(clerk_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@app.on_event("startup")
async def start_index_build():
    app.state.index_task = asyncio.create_task(ensure_indexes())


@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()
