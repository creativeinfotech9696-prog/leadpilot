import json
import os
import re

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage

PROVIDER, MODEL = "anthropic", "claude-sonnet-5-5"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

PERSONA = """You are Dialer Intelligence, a senior US call-center operations analyst embedded in the user's Primo Dialer business.
The user runs outbound and inbound campaigns using many CLIs (caller IDs) and many lead lists ("data packages").
Conversion means COMPLETED SALES only. Connect = call answered (human or machine). Contact = a human conversation.
Be direct and operational: name the exact list / CLI, the exact time window (in the user's time zone), and the numbers behind it.
Respect every operator rule in AI MEMORY - they override your own judgment. Use LEARNED OUTCOMES to weight your advice:
favour action types that worked before, be cautious with types that failed. Never invent data you were not given."""

CHAT_RULES = """Answer in concise markdown (short headings, bullets, small tables when comparing). Lead with the answer.
If the user states a lasting business rule, preference or fact about their operation (e.g. "never dial list A after 6pm",
"we pay $0.08 per lead for list B"), confirm it and add a final separate line exactly: REMEMBER: <the rule in one sentence>"""

REC_PROMPT = """Using the live dialer data above, produce 5 to 8 concrete actions for the next dialing day.
Cover lead lists (which to run, when, which to rest or replace), CLIs (rotate, rest, pair with lists) and timing.
Return ONLY valid JSON, no prose, in this shape:
{"recommendations":[{"title":"short imperative headline","category":"lead_list|cli|timing|general",
"target_type":"list|cli|none","target":"exact list or CLI name or empty","action":"what to do in the dialer, step by step in one or two sentences",
"reason":"why, referencing the numbers","evidence":"key numbers e.g. 'Connect 12.1% -> 6.3% (3d)'","priority":"high|medium|low","confidence":0-100}]}"""


def _chat(session_id: str, system: str) -> LlmChat:
    return LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=session_id, system_message=system).with_model(PROVIDER, MODEL)


async def stream(session_id: str, system: str, text: str):
    async for ev in _chat(session_id, system).stream_message(UserMessage(text=text)):
        if isinstance(ev, TextDelta):
            yield ev.content
        elif isinstance(ev, StreamDone):
            break


def _row(d: dict, keys: list) -> str:
    return ",".join(str(d.get(k, "")) for k in keys)


def build_context(a: dict, s: dict, memory: list, feedback: list) -> str:
    if not a.get("has_data"):
        return "NO DIALER DATA UPLOADED YET."
    k = a["kpis"]
    out = [f"Time zone: {s['timezone']}. Data window: {a['start'][:10]} to {a['anchor'][:10]} (last {a['window_days'] or 'all'} days).",
           f"OVERALL: dials={k['dials']} connect%={k['connect_rate']} contact%={k['contact_rate']} sales={k['sales']} "
           f"conv%={k['conv_rate']} dials/sale={k['dials_per_sale']} unique_leads={k['leads']} outbound={k['outbound']} inbound={k['inbound']}"]
    lk = ["list", "dials", "leads", "repeat", "connect_rate", "contact_rate", "sales", "conv_rate", "dials_per_sale",
          "prior_connect_rate", "recent_connect_rate", "connect_drop_pct", "score", "status", "cost_per_sale"]
    out.append("\nLEAD LISTS (" + ",".join(lk) + "; recent=last 3 days, prior=days 4-10):")
    for r in a["lists"][:30]:
        bt = "; ".join(f"{DAYS[b['weekday']]} {b['hour']}:00 conn {b['connect_rate']}% conv {b['conv_rate']}%" for b in r["best_times"])
        out.append(_row(r, lk) + (f" | best: {bt}" if bt else ""))
    out.append(f"\nCLI coverage: {k.get('cli_coverage', 0)}% of calls have a known CLI (from the dialer export or matched from carrier CDR reports). "
               "CLI stats below only cover those calls; if coverage is low, tell the user to upload the matching CDR report.")
    ck = ["cli", "area_code", "dials", "connect_rate", "conv_rate", "prior_connect_rate", "recent_connect_rate",
          "connect_drop_pct", "score", "status"]
    out.append("\nCLIs (" + ",".join(ck) + "):")
    out += [_row(r, ck) + f" | best lists: {'/'.join(r['top_lists'])}" for r in a["clis"][:30]]
    out.append("\nBEST CLI+LIST PAIRS (cli,list,dials,connect_rate,conv_rate):")
    out += [_row(p, ["cli", "list", "dials", "connect_rate", "conv_rate"]) for p in a["pairs"][:12]]
    out.append("\nHOURLY ALL LISTS (hour,dials,connect_rate,conv_rate):")
    out += [_row(h, ["hour", "dials", "connect_rate", "conv_rate"]) for h in a["hourly"]]
    out.append("\nDAILY (date,dials,connect_rate,conv_rate,sales):")
    out += [_row(d, ["date", "dials", "connect_rate", "conv_rate", "sales"]) for d in a["daily"][-14:]]
    out.append("\nDIRECTION (direction,dials,connect_rate,conv_rate,sales):")
    out += [_row(d, ["direction", "dials", "connect_rate", "conv_rate", "sales"]) for d in a["direction"]]
    for t, label in (("rule", "OPERATOR RULES (must follow)"), ("note", "OPERATOR NOTES"), ("learned", "LEARNED OUTCOMES")):
        items = [m["text"] for m in memory if m["type"] == t]
        out.append(f"\nAI MEMORY - {label}:\n" + ("\n".join(f"- {i}" for i in items) if items else "- none"))
    stats = {}
    for f in feedback:
        c = stats.setdefault(f.get("category", "general"), {"applied": 0, "worked": 0, "failed": 0, "ignored": 0})
        c[{"applied": "applied", "failed": "failed", "ignored": "ignored"}[f["status"]]] += 1
        if (f.get("outcome") or {}).get("verdict") == "worked":
            c["worked"] += 1
        if (f.get("outcome") or {}).get("verdict") == "worse":
            c["failed"] += 1
    out.append("\nRECOMMENDATION TRACK RECORD by category: " + json.dumps(stats))
    out.append("RECENT FEEDBACK:")
    for f in feedback[:20]:
        o = (f.get("outcome") or {}).get("verdict", "pending")
        out.append(f"- [{f['status']}/{o}] {f['title']}" + (f" (note: {f['feedback_note']})" if f.get("feedback_note") else ""))
    return "\n".join(out)


async def generate_recommendations(session_id: str, ctx: str) -> list:
    text = ""
    async for d in stream(session_id, PERSONA, f"=== LIVE DIALER DATA ===\n{ctx}\n\n{REC_PROMPT}"):
        text += d
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("AI did not return recommendations")
    items = json.loads(m.group(0)).get("recommendations", [])
    out = []
    for r in items:
        out.append({
            "title": str(r.get("title", ""))[:200], "category": r.get("category") if r.get("category") in ("lead_list", "cli", "timing", "general") else "general",
            "target_type": r.get("target_type") if r.get("target_type") in ("list", "cli") else "none",
            "target": str(r.get("target") or ""), "action": str(r.get("action", "")), "reason": str(r.get("reason", "")),
            "evidence": str(r.get("evidence", "")), "priority": r.get("priority") if r.get("priority") in ("high", "medium", "low") else "medium",
            "confidence": int(r.get("confidence") or 60),
        })
    return out


def chat_system(ctx: str) -> str:
    return f"{PERSONA}\n\n{CHAT_RULES}\n\n=== LIVE DIALER DATA ===\n{ctx}"


def chat_prompt(history: list, message: str) -> str:
    if not history:
        return message
    h = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:1500]}" for m in history)
    return f"Conversation so far:\n{h}\n\nUser's new message: {message}"
