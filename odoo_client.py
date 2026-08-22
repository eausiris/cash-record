"""
Odoo XML-RPC client - bakesome.co.th
"""
import xmlrpc.client
from datetime import datetime, timedelta
from config import settings


def _get_uid_and_mdl():
    common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(settings.ODOO_DB, settings.ODOO_USER, settings.ODOO_PASSWORD, {})
    if not uid:
        raise Exception("Odoo authentication failed")
    mdl = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")
    return uid, mdl


def _date_range_utc(date: str):
    dt = datetime.strptime(date, "%Y-%m-%d")
    start = dt - timedelta(hours=7)
    end   = start + timedelta(days=1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def _branch_prefix(branch: str) -> str:
    return "RM3" if branch == "rama3" else "KASET"


def get_cash_sales(date: str, branch: str) -> list:
    if not settings.ODOO_URL:
        return _fake_cash_sales(date, branch)
    try:
        uid, mdl = _get_uid_and_mdl()
        db  = settings.ODOO_DB
        pwd = settings.ODOO_PASSWORD
        dt_start, dt_end = _date_range_utc(date)
        prefix = _branch_prefix(branch)
        items = []
        configs = mdl.execute_kw(db, uid, pwd, "pos.config", "search_read",
            [[["name", "ilike", prefix]]], {"fields": ["id"]})
        config_ids = [c["id"] for c in configs]
        if config_ids:
            pos_orders = mdl.execute_kw(db, uid, pwd, "pos.order", "search_read",
                [[["config_id", "in", config_ids],
                  ["date_order", ">=", dt_start], ["date_order", "<", dt_end],
                  ["state", "in", ["done", "paid"]], ["amount_total", ">", 0]]],
                {"fields": ["name", "partner_id", "amount_total"], "limit": 500, "order": "date_order asc"})
            for o in pos_orders:
                items.append({
                    "odoo_ref":      o["name"],
                    "customer_name": o["partner_id"][1] if o.get("partner_id") else "ลูกค้าทั่วไป",
                    "sale_type":     "pos",
                    "odoo_amount":   o.get("amount_total", 0),
                })
        payments = mdl.execute_kw(db, uid, pwd, "account.payment", "search_read",
            [[["date", "=", date], ["payment_type", "=", "inbound"],
              ["journal_id.type", "=", "cash"], ["state", "=", "posted"]]],
            {"fields": ["name", "partner_id", "amount"], "limit": 200})
        for p in payments:
            items.append({
                "odoo_ref":      p["name"],
                "customer_name": p["partner_id"][1] if p.get("partner_id") else "-",
                "sale_type":     "invoice",
                "odoo_amount":   p.get("amount", 0),
            })
        return items
    except Exception as e:
        print(f"Odoo error: {e}")
        return _fake_cash_sales(date, branch)


def get_odoo_cash(date: str, branch: str) -> dict:
    return {"pos": 0.0, "inv": 0.0, "exp": 0.0, "net": 0.0}


def _fake_cash_sales(date: str, branch: str) -> list:
    import random
    seed = int(date.replace("-", "")) + (1 if branch == "rama3" else 2)
    rng = random.Random(seed)
    customers = ["บ.สยามเทค จก.", "ร.อรุณพาณิชย์", "คุณสมชาย", "ลูกค้าทั่วไป"]
    items = []
    for i in range(rng.randint(4, 9)):
        t = "pos" if rng.random() > 0.3 else "invoice"
        ref = f"POS/{date}/{1000+i}" if t == "pos" else f"INV/{date}/{500+i}"
        items.append({"odoo_ref": ref, "customer_name": rng.choice(customers),
                      "sale_type": t, "odoo_amount": round(rng.uniform(500, 25000), 2)})
    return items


def _fake_odoo(date: str, branch: str) -> dict:
    return {"pos": 0.0, "inv": 0.0, "exp": 0.0, "net": 0.0}
