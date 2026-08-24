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
            non_cash_methods = mdl.execute_kw(db, uid, pwd, "pos.payment.method", "search_read",
                [[["journal_id.type", "!=", "cash"]]],
                {"fields": ["id"], "limit": 100})
            non_cash_method_ids = [m["id"] for m in non_cash_methods]

            non_cash_order_ids = []
            if non_cash_method_ids:
                non_cash_payments = mdl.execute_kw(db, uid, pwd, "pos.payment", "search_read",
                    [[["payment_method_id", "in", non_cash_method_ids],
                      ["pos_order_id.config_id", "in", config_ids],
                      ["pos_order_id.date_order", ">=", dt_start],
                      ["pos_order_id.date_order", "<", dt_end]]],
                    {"fields": ["pos_order_id"], "limit": 1000})
                non_cash_order_ids = list({p["pos_order_id"][0] for p in non_cash_payments if p.get("pos_order_id")})

            # Cash orders (not non-cash) OR refunds (negative amount, always include)
            exclude = non_cash_order_ids if non_cash_order_ids else [-1]
            domain = [
                ["config_id", "in", config_ids],
                ["date_order", ">=", dt_start],
                ["date_order", "<",  dt_end],
                ["state", "in", ["done", "paid", "invoiced", "return", "returned"]],
                "|",
                ["id", "not in", exclude],
                ["amount_total", "<", 0],
            ]

            pos_orders = mdl.execute_kw(db, uid, pwd, "pos.order", "search_read",
                [domain],
                {"fields": ["name", "partner_id", "amount_total", "date_order"], "limit": 500,
                 "order": "date_order asc"})
            for o in pos_orders:
                # แปลง UTC → UTC+7
                raw_dt = o.get("date_order", "")
                try:
                    from datetime import timezone
                    dt_utc = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    dt_local = dt_utc + timedelta(hours=7)
                    bill_time = dt_local.strftime("%H:%M")
                except Exception:
                    bill_time = ""
                items.append({
                    "odoo_ref":      o["name"],
                    "customer_name": o["partner_id"][1] if o.get("partner_id") else "ลูกค้าทั่วไป",
                    "sale_type":     "pos",
                    "odoo_amount":   o.get("amount_total", 0),
                    "bill_time":     bill_time,
                })

        payments = mdl.execute_kw(db, uid, pwd, "account.payment", "search_read",
            [[["date", "=", date],
              ["payment_type", "=", "inbound"],
              ["journal_id.type", "=", "cash"],
              ["state", "=", "posted"]]],
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
        print(f"Odoo get_cash_sales error: {e}")
        raise


def get_order_lines(odoo_ref: str) -> list:
    try:
        uid, mdl = _get_uid_and_mdl()
        db  = settings.ODOO_DB
        pwd = settings.ODOO_PASSWORD
        orders = mdl.execute_kw(db, uid, pwd, "pos.order", "search_read",
            [[["name", "=", odoo_ref]]],
            {"fields": ["id"], "limit": 1})
        if not orders:
            return []
        order_id = orders[0]["id"]
        lines = mdl.execute_kw(db, uid, pwd, "pos.order.line", "search_read",
            [[["order_id", "=", order_id]]],
            {"fields": ["product_id", "qty", "price_unit", "price_subtotal_incl"], "limit": 100})
        return [{
            "product_name": l["product_id"][1] if l.get("product_id") else "-",
            "qty": l.get("qty", 0),
            "price_unit": l.get("price_unit", 0),
            "price_subtotal": l.get("price_subtotal_incl", 0),
        } for l in lines]
    except Exception as e:
        print(f"get_order_lines error: {e}")
        raise
