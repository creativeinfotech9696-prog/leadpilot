import hashlib
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
# name: (pool size, base connect, sale rate per contact, decay per day)
LISTS = {
    "FL-Medicare-T65-Oct": (2600, 0.30, 0.060, 0.004),
    "TX-FinalExpense-Aged30": (1500, 0.24, 0.040, 0.012),
    "CA-ACA-Fresh-Nov": (4000, 0.34, 0.050, 0.002),
    "MultiState-Debt-Q3": (1000, 0.20, 0.025, 0.010),
    "NY-Solar-Homeowners": (2200, 0.27, 0.035, 0.003),
    "GA-AutoWarranty-Aged": (900, 0.15, 0.012, 0.006),
}
CLIS = ["3055550142", "8135550178", "2145550193", "7135550120", "2135550165", "6195550111", "4045550187", "7185550134"]
SPAM_CLI = "2145550193"
HOUR_W = {9: 0.8, 10: 1.15, 11: 1.2, 12: 0.95, 13: 0.85, 14: 0.9, 15: 1.0, 16: 1.15, 17: 1.2, 18: 1.05, 19: 0.8, 20: 0.65}
DOW_W = [1.0, 1.08, 1.1, 1.05, 0.9, 0.75, 0.6]


def generate(upload_id: str, days: int = 21, per_day: int = 1300) -> list:
    rnd = random.Random(42)
    today = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    pools = {n: [f"{rnd.randint(201, 989)}{rnd.randint(2000000, 9999999)}" for _ in range(p[0])] for n, p in LISTS.items()}
    names = list(LISTS)
    docs = []
    for d in range(days, 0, -1):
        day = today - timedelta(days=d)
        dow = day.weekday()
        if dow == 6 and rnd.random() < 0.7:
            continue
        for _ in range(int(per_day * DOW_W[dow])):
            name = rnd.choice(names)
            pool, base, sale_p, decay = LISTS[name]
            hour = rnd.choice(list(HOUR_W))
            cli = rnd.choice(CLIS)
            inbound = rnd.random() < 0.08
            conn = base * HOUR_W[hour] * DOW_W[dow] * max(0.25, 1 - decay * (days - d) * 1.6)
            if cli == SPAM_CLI and d <= 4:
                conn *= 0.35
            if inbound:
                conn = 0.92
            r = rnd.random()
            if r < conn * 0.55:
                sale_boost = 1.6 if hour in (11, 17) else 1.0
                disp = "SALE" if rnd.random() < sale_p * sale_boost * (3 if inbound else 1) * 2.2 else rnd.choice(
                    ["NOT INTERESTED", "NOT INTERESTED", "CALLBACK", "DNC", "HANGUP"])
                talk = rnd.randint(240, 1500) if disp == "SALE" else rnd.randint(15, 240)
            elif r < conn:
                disp, talk = "ANSWERING MACHINE", rnd.randint(3, 25)
            else:
                disp, talk = rnd.choice(["NO ANSWER", "NO ANSWER", "NO ANSWER", "BUSY", "DROP"]), 0
            local = day.replace(hour=hour, minute=rnd.randint(0, 59), second=rnd.randint(0, 59))
            ts = local.astimezone(timezone.utc).replace(tzinfo=None)
            phone = rnd.choice(pools[name])
            key = hashlib.md5(f"demo|{phone}|{ts}|{cli}|{disp}|{rnd.random()}".encode()).hexdigest()
            docs.append({"list": name, "cli": cli, "phone": phone, "ts": ts,
                         "direction": "inbound" if inbound else "outbound", "disposition": disp,
                         "talk_time": float(talk), "agent": f"Agent {rnd.randint(1, 12)}", "key": key,
                         "upload_id": upload_id})
    return docs
