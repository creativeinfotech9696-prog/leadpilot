import json
import re
from datetime import timedelta

import numpy as np
import pandas as pd

CATEGORIES = ["sale", "contact", "connected", "none"]
KEYWORDS = [
    ("sale", ["SALE", "SOLD", "CLOSED", "SLD"]),
    ("connected", ["MACHINE", "VOICEMAIL", "VM", "AM", "AA", "AL", "AFAX", "FAX"]),
    ("none", ["NO ANSWER", "NOANSWER", "NA", "N", "B", "BUSY", "DROP", "PDROP", "FAIL", "DISCONNECT", "DC", "ADC",
              "INVALID", "CONGEST", "DEAD", "ERI", "NEW", "QUEUE", "INCALL", "DISPO", "TIMEOUT", "UNREACHABLE"]),
    ("contact", ["INTEREST", "NI", "CALL BACK", "CALLBACK", "CALLBK", "CB", "DNC", "XFER", "TRANSFER", "PITCH", "NP",
                 "HUMAN", "ANSWER", "LANG", "WRONG", "HANG", "HU", "DEC", "DECLINE", "NOT QUAL", "NQ", "QUALIFIED", "LEAD"]),
]
PROJ = {"_id": 0, "call_id": 1, "list": 1, "cli": 1, "phone": 1, "ts": 1, "direction": 1, "disposition": 1, "talk_time": 1}
STATUS_ACTIONS = {
    "list": {"Keep": "Keep running", "Watch": "Monitor - run only in best hours", "Rest": "Rest 3-5 days",
             "Replace": "Replace with fresh data"},
    "cli": {"Keep": "Keep in rotation", "Watch": "Reduce volume", "Rest": "Rotate out & rest 48-72h",
            "Replace": "Retire & replace number"},
}


def guess_category(d: str) -> str:
    d = (d or "").upper().strip()
    words = set(re.split(r"[^A-Z0-9]+", d))
    for cat, keys in KEYWORDS:
        for k in keys:
            if (len(k) <= 3 and k in words) or (len(k) > 3 and k in d):
                return cat
    return "none"


async def load_df(db, days: int, flt: dict | None = None):
    latest = await db.calls.find_one(flt or {}, {"ts": 1}, sort=[("ts", -1)])
    if not latest:
        return pd.DataFrame(), None
    anchor = latest["ts"]
    q = dict(flt or {})
    if days:
        q["ts"] = {"$gte": anchor - timedelta(days=days)}
    docs = await db.calls.find(q, PROJ).to_list(None)
    return pd.DataFrame(docs), anchor


def prepare(df: pd.DataFrame, s: dict) -> pd.DataFrame:
    df = df.copy()
    for c in ["list", "cli", "phone", "direction", "disposition"]:
        if c not in df:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str)
    df["talk_time"] = pd.to_numeric(df.get("talk_time", 0), errors="coerce").fillna(0)
    df["ts"] = pd.to_datetime(df["ts"])
    local = df["ts"].dt.tz_localize("UTC").dt.tz_convert(s["timezone"])
    df["hour"] = local.dt.hour
    df["weekday"] = local.dt.weekday
    df["date"] = local.dt.strftime("%Y-%m-%d")
    dmap = s.get("disposition_map", {})
    disp = df["disposition"].str.upper().str.strip()
    cats = {u: dmap.get(u) or guess_category(u) for u in disp.unique()}
    cat = disp.map(cats)
    df["sale"] = cat == "sale"
    df["contact"] = df["sale"] | (cat == "contact")
    df["connect"] = df["contact"] | (cat == "connected")
    return df


def add_rates(g: pd.DataFrame) -> pd.DataFrame:
    d = g["dials"].replace(0, np.nan)
    g["connect_rate"] = (g["connects"] / d * 100).round(2)
    g["contact_rate"] = (g["contacts"] / d * 100).round(2)
    g["conv_rate"] = (g["sales"] / d * 100).round(3)
    g["avg_talk"] = (g["talk"] / g["contacts"].replace(0, np.nan)).round(0)
    g["dials_per_sale"] = (g["dials"] / g["sales"].replace(0, np.nan)).round(0)
    g["repeat"] = (g["dials"] / g["leads"].replace(0, np.nan)).round(2)
    return g.fillna(0)


def summarize(df: pd.DataFrame, keys: list) -> pd.DataFrame:
    g = df.groupby(keys).agg(
        dials=("sale", "size"), connects=("connect", "sum"), contacts=("contact", "sum"),
        sales=("sale", "sum"), talk=("talk_time", "sum"), leads=("phone", "nunique"),
    ).reset_index()
    return add_rates(g)


def records(g: pd.DataFrame) -> list:
    return json.loads(g.to_json(orient="records"))


def rates(df: pd.DataFrame) -> dict:
    df = df.assign(_k=1)
    r = records(summarize(df, ["_k"]))[0]
    r.pop("_k", None)
    return r


def trend(df: pd.DataFrame, key: str, anchor) -> pd.DataFrame:
    cut, start = anchor - timedelta(days=3), anchor - timedelta(days=10)
    r = df[df["ts"] >= cut].groupby(key).agg(recent_dials=("connect", "size"), rc=("connect", "mean"))
    p = df[(df["ts"] < cut) & (df["ts"] >= start)].groupby(key).agg(prior_dials=("connect", "size"), pc=("connect", "mean"))
    t = r.join(p, how="outer").fillna(0)
    ok = (t["recent_dials"] >= 30) & (t["prior_dials"] >= 30) & (t["pc"] > 0)
    t["connect_drop_pct"] = np.where(ok, (t["pc"] - t["rc"]) / t["pc"].replace(0, np.nan) * 100, 0).round(1)
    t["recent_connect_rate"] = (t["rc"] * 100).round(2)
    t["prior_connect_rate"] = (t["pc"] * 100).round(2)
    return t.drop(columns=["rc", "pc"]).reset_index()


def score_row(r: dict, ov: dict, s: dict, kind: str) -> dict:
    cr = r["connect_rate"] / ov["connect_rate"] if ov["connect_rate"] else 1
    vr = r["conv_rate"] / ov["conv_rate"] if ov["conv_rate"] else 1
    drop = max(r.get("connect_drop_pct", 0), 0)
    sc = 50 * min(cr, 1.5) / 1.5 + 35 * min(vr, 1.5) / 1.5
    sc += 15 * (1 - min(max(r["repeat"] - 1, 0) / 4, 1)) if kind == "list" else 15
    sc = round(max(0, min(100, sc - min(drop * 0.5, 35))))
    reasons = [f"Connect {r['connect_rate']:.1f}% vs {ov['connect_rate']:.1f}% avg",
               f"Conversion {r['conv_rate']:.2f}% vs {ov['conv_rate']:.2f}% avg"]
    if drop >= 10:
        reasons.append(f"Connect rate down {drop:.0f}% in last 3 days ({r['prior_connect_rate']:.1f}% -> {r['recent_connect_rate']:.1f}%)")
    if kind == "list" and r["repeat"] >= 2:
        reasons.append(f"Each lead dialed {r['repeat']:.1f}x on average - list is wearing out")
    if r["dials"] < s["min_dials"]:
        status = "Watch"
        reasons.insert(0, f"Only {r['dials']} dials - not enough data yet")
    elif kind == "cli" and drop >= s["cli_drop_pct"] and r.get("recent_dials", 0) >= 30:
        status = "Rest"
        reasons.insert(0, "Answer rate collapsing - likely spam-flagged")
    elif kind == "list" and r["repeat"] >= 3 and drop >= s["list_drop_pct"]:
        status = "Replace"
        reasons.insert(0, "List exhausted: heavy redials and falling connects")
    elif sc >= 65:
        status = "Keep"
    elif sc >= 45:
        status = "Watch"
    elif sc >= 30:
        status = "Rest"
    else:
        status = "Replace"
    return {**r, "score": sc, "status": status, "action": STATUS_ACTIONS[kind][status], "reasons": reasons}


def best_cells(cells: pd.DataFrame, min_d: int, n: int = 3) -> list:
    c = cells[cells["dials"] >= min_d].copy()
    if c.empty:
        return []
    c["rank"] = c["connect_rate"] + c["conv_rate"] * 10
    return records(c.sort_values("rank", ascending=False).head(n)[["weekday", "hour", "dials", "connect_rate", "conv_rate"]])


def analyze(df: pd.DataFrame, s: dict, anchor, window_days: int) -> dict:
    if df.empty:
        return {"has_data": False}
    df = prepare(df, s)
    ov = rates(df)
    cut = anchor - timedelta(days=3)
    lists = summarize(df, ["list"]).merge(trend(df, "list", anchor), on="list", how="left").fillna(0)
    cdf = df[df["cli"] != "Unknown"]
    if cdf.empty:
        clis, pr = pd.DataFrame(), []
    else:
        clis = summarize(cdf, ["cli"]).merge(trend(cdf, "cli", anchor), on="cli", how="left").fillna(0)
        pairs = summarize(cdf, ["cli", "list"])
        pr = records(pairs[pairs["dials"] >= max(20, s["min_dials"] // 3)].sort_values(["conv_rate", "connect_rate"], ascending=False))
    per_cell = summarize(df, ["list", "weekday", "hour"])
    all_cell = summarize(df, ["weekday", "hour"]).assign(list="__all__")
    cell_min = max(15, s["min_dials"] // 10)
    costs = s.get("list_costs", {})

    list_rows = []
    for r in records(lists):
        row = score_row(r, ov, s, "list")
        row["best_times"] = best_cells(per_cell[per_cell["list"] == r["list"]], cell_min)
        cost = costs.get(r["list"])
        row["cost"] = cost
        row["cost_per_sale"] = round(cost / r["sales"], 2) if cost and r["sales"] else None
        list_rows.append(row)
    cli_rows = []
    for r in ([] if clis.empty else records(clis)):
        row = score_row(r, ov, s, "cli")
        digits = re.sub(r"\D", "", r["cli"])[-10:]
        row["area_code"] = digits[:3] if len(digits) == 10 else ""
        row["top_lists"] = [p["list"] for p in pr if p["cli"] == r["cli"]][:3]
        cli_rows.append(row)
    list_rows.sort(key=lambda x: -x["dials"])
    cli_rows.sort(key=lambda x: -x["dials"])
    recent = df[df["ts"] >= cut]
    kpis = {**ov, "inbound": int((df["direction"] == "inbound").sum()), "outbound": int((df["direction"] != "inbound").sum()),
            "total_lists": len(list_rows), "active_lists": int(recent["list"].nunique()), "total_clis": len(cli_rows),
            "flagged_clis": sum(1 for c in cli_rows if c["status"] in ("Rest", "Replace")),
            "lists_to_replace": sum(1 for x in list_rows if x["status"] in ("Rest", "Replace")),
            "cli_coverage": round(float((df["cli"] != "Unknown").mean()) * 100, 1)}
    heat = pd.concat([all_cell, per_cell])[["list", "weekday", "hour", "dials", "sales", "connect_rate", "conv_rate"]]
    daily = summarize(df, ["date"]).sort_values("date")
    daily = daily[daily["dials"] >= daily["dials"].median() * 0.15]
    return {
        "has_data": True, "anchor": anchor.isoformat(), "start": df["ts"].min().isoformat(),
        "window_days": window_days, "timezone": s["timezone"], "kpis": kpis,
        "daily": records(daily),
        "hourly": records(summarize(df, ["hour"]).sort_values("hour")),
        "direction": records(summarize(df, ["direction"])),
        "lists": list_rows, "clis": cli_rows, "pairs": pr[:20],
        "best_overall": best_cells(all_cell, cell_min, 5),
        "heatmap": records(heat),
    }


def compare(before: pd.DataFrame, after: pd.DataFrame, s: dict) -> dict | None:
    if len(after) < max(50, s["min_dials"] // 2) or len(before) < 50:
        return None
    b, a = rates(prepare(before, s)), rates(prepare(after, s))

    def rel(k):
        return (a[k] - b[k]) / b[k] if b[k] else (1 if a[k] > 0 else 0)
    score = rel("conv_rate") * 0.6 + rel("connect_rate") * 0.4
    verdict = "worked" if score > 0.05 else "worse" if score < -0.05 else "no_change"
    return {"verdict": verdict, "before": {k: b[k] for k in ("dials", "connect_rate", "conv_rate")},
            "after": {k: a[k] for k in ("dials", "connect_rate", "conv_rate")}, "score": round(score * 100, 1)}
