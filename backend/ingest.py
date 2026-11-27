import hashlib
import io
import re
from datetime import timezone
from zoneinfo import ZoneInfo

import pandas as pd
from dateutil import parser as dtparser

CALL_ID = ["uniqueid", "callid", "calluuid", "uuid", "linkedid", "calluniqueid", "callreference", "callref"]
TS = ["calldate", "datetime", "calldatetime", "starttime", "calltime", "timestamp", "date", "eventtime",
      "createdat", "start", "answertime"]
FIELDS = {
    "call_id": CALL_ID,
    "list": ["listname", "list", "listid", "leadlist", "campaign", "campaignname", "campaignid", "leadpackage",
             "package", "datapackage", "source", "leadsource"],
    "cli": ["cli", "callerid", "outboundcid", "cid", "did", "callernumber", "fromnumber", "dialedfrom", "ani"],
    "phone": ["phonenumber", "phone", "customerphone", "customernumber", "number", "leadphone", "tonumber",
              "dst", "dialednumber", "mobile", "destination"],
    "timestamp": TS,
    "time": ["time", "timeofcall"],
    "direction": ["direction", "calltype", "type", "inout", "inboundoutbound"],
    "disposition": ["disposition", "status", "dispo", "callstatus", "result", "outcome", "statusname",
                    "dispositionname", "dispositioncode"],
    "talk_time": ["talktime", "talksec", "billsec", "duration", "lengthinsec", "talkduration", "callduration",
                  "length", "seconds"],
    "agent": ["agent", "user", "agentname", "username", "fullname", "agentid", "rep"],
}
REQUIRED = ["list", "timestamp", "disposition"]
CDR_FIELDS = {
    "call_id": CALL_ID,
    "from": ["callerid", "cli", "src", "source", "sourcenumber", "fromnumber", "from", "caller", "callingnumber",
             "callingparty", "ani", "clid", "origination", "outboundcid"],
    "to": ["dst", "destination", "destinationnumber", "tonumber", "to", "callednumber", "calledparty", "dialednumber",
           "dnis", "phonenumber", "phone", "number", "customernumber"],
    "timestamp": TS,
    "time": ["time", "timeofcall"],
    "duration": ["billsec", "duration", "billableseconds", "seconds", "length", "talktime", "callduration"],
}
CDR_REQUIRED = ["from", "to", "timestamp"]


def _norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


def read_bytes(data: bytes, ext: str) -> pd.DataFrame:
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)
    else:
        df = pd.read_csv(io.BytesIO(data), dtype=str, sep=None, engine="python", encoding_errors="replace", keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df.fillna("")


def signature(cols: list) -> str:
    return "|".join(sorted(_norm(c) for c in cols))


def suggest(cols: list, kind: str = "calls") -> dict:
    fields = CDR_FIELDS if kind == "cdr" else FIELDS
    normed = {c: _norm(c) for c in cols}
    used, out = set(), {}
    for exact in (True, False):
        for field, syns in fields.items():
            if field in out:
                continue
            for syn in syns:
                hit = next((c for c, n in normed.items() if c not in used and (n == syn if exact else syn in n)), None)
                if hit:
                    out[field] = hit
                    used.add(hit)
                    break
    return {f: out.get(f) for f in fields}


def disposition_counts(df: pd.DataFrame, col: str | None) -> list:
    if not col or col not in df:
        return []
    vc = df[col].astype(str).str.upper().str.strip().replace("", "(BLANK)").value_counts()
    return [{"name": k, "count": int(v)} for k, v in vc.items()][:200]


def _talk(s: pd.Series) -> pd.Series:
    n = pd.to_numeric(s, errors="coerce")
    m = n.isna() & s.str.contains(":", na=False)
    if m.any():
        t = s[m].where(s[m].str.count(":") == 2, "00:" + s[m])
        n[m] = pd.to_timedelta(t, errors="coerce").dt.total_seconds()
    return n.fillna(0)


def _col(df, mapping, f, default=""):
    c = mapping.get(f)
    return df[c].astype(str).str.strip() if c and c in df else pd.Series(default, index=df.index)


def _digits(s: pd.Series) -> pd.Series:
    return s.str.replace(r"\D", "", regex=True).str[-10:]


TZ_ABBR = {k: h * 3600 for k, h in {"UTC": 0, "GMT": 0, "Z": 0, "EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7,
                                      "MDT": -6, "PST": -8, "PDT": -7, "IST": 5.5, "PKT": 5}.items()}


def _parse_one(v: str, zone: ZoneInfo):
    try:
        d = dtparser.parse(v, tzinfos=TZ_ABBR)
    except (ValueError, OverflowError, TypeError):
        return pd.NaT
    if d.tzinfo is None:
        d = d.replace(tzinfo=zone)
    return d.astimezone(timezone.utc).replace(tzinfo=None)


def parse_ts(df, mapping, tz) -> pd.Series:
    raw = _col(df, mapping, "timestamp").str.strip()
    if mapping.get("time"):
        raw = raw + " " + _col(df, mapping, "time").str.strip()
    nonblank = raw[raw != ""]
    if len(nonblank) and nonblank.str.fullmatch(r"\d{10}(\d{3})?(\.\d+)?").all():  # unix epoch seconds / ms
        n = pd.to_numeric(raw, errors="coerce")
        return pd.to_datetime(n, unit="ms" if n.max() > 1e11 else "s", errors="coerce")
    try:
        has_offset = raw.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
        naive = pd.to_datetime(raw.where(~has_offset), errors="coerce", format="mixed")
        naive = naive.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
        aware = pd.to_datetime(raw.where(has_offset), errors="coerce", format="mixed", utc=True)
        return aware.where(has_offset, naive).dt.tz_localize(None)
    except (ValueError, TypeError):  # time-zone names / mixed styles: parse each distinct value
        zone = ZoneInfo(tz)
        lookup = {v: _parse_one(v, zone) for v in raw.unique()}
        return pd.to_datetime(raw.map(lookup), errors="coerce")


def build_docs(df: pd.DataFrame, mapping: dict, tz: str, upload_id: str) -> tuple[list, int]:
    def col(f, default=""):
        return _col(df, mapping, f, default)

    ts = parse_ts(df, mapping, tz)
    direction = col("direction").str.lower()
    cli_raw = col("cli")
    cli = cli_raw.str.replace(r"\D", "", regex=True)
    out = pd.DataFrame({
        "list": col("list").replace("", "Unassigned"),
        "cli": cli.where(cli != "", cli_raw).replace("", "Unknown"),
        "phone": _digits(col("phone")),
        "call_id": col("call_id"),
        "ts": ts,
        "direction": direction.apply(lambda d: "inbound" if d.startswith("in") or "inbound" in d else "outbound"),
        "disposition": col("disposition").str.upper().replace("", "(BLANK)"),
        "talk_time": _talk(col("talk_time", "0")),
        "agent": col("agent"),
    })
    out = out[out["ts"].notna()]
    invalid = len(df) - len(out)
    key_src = out["phone"] + "|" + out["ts"].astype(str) + "|" + out["cli"] + "|" + out["disposition"] + "|" + out["list"]
    out["key"] = key_src.map(lambda k: hashlib.md5(k.encode()).hexdigest())
    out["upload_id"] = upload_id
    recs = out.to_dict("records")
    for r in recs:
        r["ts"] = r["ts"].to_pydatetime()
    return recs, invalid


def build_cdr_docs(df: pd.DataFrame, mapping: dict, tz: str, upload_id: str) -> tuple[list, int]:
    out = pd.DataFrame({
        "from": _digits(_col(df, mapping, "from")), "to": _digits(_col(df, mapping, "to")),
        "ts": parse_ts(df, mapping, tz), "call_id": _col(df, mapping, "call_id"),
        "duration": _talk(_col(df, mapping, "duration", "0")),
    })
    out = out[out["ts"].notna() & ((out["from"] != "") | (out["to"] != ""))]
    invalid = len(df) - len(out)
    src = out["from"] + "|" + out["to"] + "|" + out["ts"].astype(str) + "|" + out["call_id"]
    out["key"] = src.map(lambda k: hashlib.md5(k.encode()).hexdigest())
    out["upload_id"] = upload_id
    recs = out.to_dict("records")
    for r in recs:
        r["ts"] = r["ts"].to_pydatetime()
    return recs, invalid


def match_cli(calls: pd.DataFrame, cdr: pd.DataFrame, tol_sec: int) -> pd.DataFrame:
    """Return rows (_id, cli, upload_id) for calls matched to a CDR leg."""
    calls = calls.copy()
    cdr = cdr.copy()
    for d in (calls, cdr):
        d["ts"] = pd.to_datetime(d["ts"]).astype("datetime64[ns]")
        d["call_id"] = d.get("call_id", pd.Series("", index=d.index)).fillna("").astype(str)
    calls["phone"] = calls["phone"].fillna("").astype(str)
    calls["direction"] = calls.get("direction", "outbound")
    inbound = calls["direction"] == "inbound"
    cli = pd.Series(pd.NA, index=calls.index, dtype=object)
    up = pd.Series(pd.NA, index=calls.index, dtype=object)
    ids = cdr[cdr["call_id"] != ""].drop_duplicates("call_id").set_index("call_id")
    if not ids.empty:
        has = calls["call_id"] != ""
        f, t = calls.loc[has, "call_id"].map(ids["from"]), calls.loc[has, "call_id"].map(ids["to"])
        cli[has] = t.where(inbound[has], f)
        up[has] = calls.loc[has, "call_id"].map(ids["upload_id"])
    rest = calls[cli.isna() & (calls["phone"] != "")].reset_index()[["index", "ts", "phone"]].sort_values("ts")
    tol = pd.Timedelta(seconds=tol_sec)
    legs = {}
    for side, other in (("to", "from"), ("from", "to")):
        c = cdr[cdr[side] != ""][["ts", side, other, "upload_id"]].rename(columns={side: "phone", other: "m_cli", "upload_id": "m_up"}).sort_values("ts")
        if rest.empty or c.empty:
            legs[side] = pd.DataFrame(columns=["m_cli", "m_up"])
            continue
        legs[side] = pd.merge_asof(rest, c, on="ts", by="phone", direction="nearest", tolerance=tol).set_index("index")[["m_cli", "m_up"]]
    a = legs["to"].reindex(calls.index)  # outbound leg: customer is the callee, CLI is the caller
    b = legs["from"].reindex(calls.index)  # inbound leg: customer is the caller, CLI is the DID dialled
    pick_cli = b["m_cli"].fillna(a["m_cli"]).where(inbound, a["m_cli"].fillna(b["m_cli"]))
    pick_up = b["m_up"].where(b["m_cli"].notna(), a["m_up"]).where(inbound, a["m_up"].where(a["m_cli"].notna(), b["m_up"]))
    cli = cli.fillna(pick_cli)
    up = up.fillna(pick_up)
    res = pd.DataFrame({"_id": calls["_id"], "cli": cli, "upload_id": up})
    res = res[res["cli"].notna() & (res["cli"] != "")]
    return res
