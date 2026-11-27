import hashlib
import io
import re

import pandas as pd

FIELDS = {
    "list": ["listname", "list", "listid", "leadlist", "campaign", "campaignname", "campaignid", "leadpackage",
             "package", "datapackage", "source", "leadsource"],
    "cli": ["cli", "callerid", "outboundcid", "cid", "did", "callernumber", "fromnumber", "dialedfrom", "ani"],
    "phone": ["phonenumber", "phone", "customerphone", "customernumber", "number", "leadphone", "tonumber",
              "dst", "dialednumber", "mobile", "destination"],
    "timestamp": ["calldate", "datetime", "calldatetime", "starttime", "calltime", "timestamp", "date", "eventtime",
                  "createdat", "start"],
    "time": ["time", "timeofcall"],
    "direction": ["direction", "calltype", "type", "inout", "inboundoutbound"],
    "disposition": ["disposition", "status", "dispo", "callstatus", "result", "outcome", "statusname",
                    "dispositionname", "dispositioncode"],
    "talk_time": ["talktime", "talksec", "billsec", "duration", "lengthinsec", "talkduration", "callduration",
                  "length", "seconds"],
    "agent": ["agent", "user", "agentname", "username", "fullname", "agentid", "rep"],
}
REQUIRED = ["list", "timestamp", "disposition"]


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


def suggest(cols: list) -> dict:
    normed = {c: _norm(c) for c in cols}
    used, out = set(), {}
    for exact in (True, False):
        for field, syns in FIELDS.items():
            if field in out:
                continue
            for syn in syns:
                hit = next((c for c, n in normed.items() if c not in used and (n == syn if exact else syn in n)), None)
                if hit:
                    out[field] = hit
                    used.add(hit)
                    break
    return {f: out.get(f) for f in FIELDS}


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


def build_docs(df: pd.DataFrame, mapping: dict, tz: str, upload_id: str) -> tuple[list, int]:
    def col(f, default=""):
        c = mapping.get(f)
        return df[c].astype(str).str.strip() if c and c in df else pd.Series(default, index=df.index)

    raw = col("timestamp")
    if mapping.get("time"):
        raw = raw + " " + col("time")
    ts = pd.to_datetime(raw, errors="coerce", format="mixed")
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    direction = col("direction").str.lower()
    cli_raw = col("cli")
    cli = cli_raw.str.replace(r"\D", "", regex=True)
    out = pd.DataFrame({
        "list": col("list").replace("", "Unassigned"),
        "cli": cli.where(cli != "", cli_raw).replace("", "Unknown"),
        "phone": col("phone").str.replace(r"\D", "", regex=True).str[-10:],
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
