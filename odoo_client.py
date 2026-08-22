"""
Odoo XML-RPC client
ดึงยอดเงินสดจาก Odoo account.bank.statement หรือ pos.session
"""
import xmlrpc.client
from config import settings

def get_odoo_cash(date: str, branch: str) -> dict:
    """
    ดึงยอดเงินสดจาก Odoo สำหรับวันที่และสาขาที่กำหนด
    คืนค่า dict: {pos, inv, exp, net}
    """
    if not settings.ODOO_URL:
        # ถ้ายังไม่ได้ตั้งค่า Odoo ให้คืนค่าจำลอง
        return _fake_odoo(date, branch)

    try:
        common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
        uid = common.authenticate(settings.ODOO_DB, settings.ODOO_USER, settings.ODOO_PASSWORD, {})
        if not uid:
            raise Exception("Odoo authentication failed")

        models = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")

        # Map branch name to Odoo journal/pos config name (ปรับตาม config จริง)
        branch_map = {"rama3": "Rama 3", "kaset": "Kaset"}
        branch_name = branch_map.get(branch, branch)

        # ดึงยอด POS session ของวันนั้น
        pos_sessions = models.execute_kw(
            settings.ODOO_DB, uid, settings.ODOO_PASSWORD,
            "pos.session", "search_read",
            [[["start_at", ">=", f"{date} 00:00:00"],
              ["start_at", "<=", f"{date} 23:59:59"],
              ["config_id.name", "ilike", branch_name],
              ["state", "=", "closed"]]],
            {"fields": ["cash_register_total_entry_encoding", "cash_register_difference"], "limit": 5}
        )
        pos_total = sum(s.get("cash_register_total_entry_encoding", 0) for s in pos_sessions)

        # ยอดรับชำระสด (account move lines)
        inv_payments = models.execute_kw(
            settings.ODOO_DB, uid, settings.ODOO_PASSWORD,
            "account.payment", "search_read",
            [[["date", "=", date],
              ["payment_type", "=", "inbound"],
              ["journal_id.type", "=", "cash"],
              ["state", "=", "posted"]]],
            {"fields": ["amount"], "limit": 200}
        )
        inv_total = sum(p.get("amount", 0) for p in inv_payments)

        # ยอดจ่ายสด (outbound)
        exp_payments = models.execute_kw(
            settings.ODOO_DB, uid, settings.ODOO_PASSWORD,
            "account.payment", "search_read",
            [[["date", "=", date],
              ["payment_type", "=", "outbound"],
              ["journal_id.type", "=", "cash"],
              ["state", "=", "posted"]]],
            {"fields": ["amount"], "limit": 200}
        )
        exp_total = sum(p.get("amount", 0) for p in exp_payments)

        net = pos_total + inv_total - exp_total
        return {"pos": pos_total, "inv": inv_total, "exp": exp_total, "net": net}

    except Exception as e:
        # fallback จำลองถ้า Odoo error
        print(f"Odoo error: {e}")
        return _fake_odoo(date, branch)


def get_cash_sales(date: str, branch: str) -> list:
    """
    ดึงรายการขายเงินสดแต่ละรายการจาก Odoo (POS orders + cash invoices)
    คืนค่า list of dict: {odoo_ref, customer_name, sale_type, odoo_amount}
    """
    if not settings.ODOO_URL:
        return _fake_cash_sales(date, branch)

    try:
        common = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
        uid = common.authenticate(settings.ODOO_DB, settings.ODOO_USER, settings.ODOO_PASSWORD, {})
        mdl = xmlrpc.client.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")

        branch_map = {"rama3": "Rama 3", "kaset": "Kaset"}
        branch_name = branch_map.get(branch, branch)
        items = []

        # POS orders
        pos_orders = mdl.execute_kw(
            settings.ODOO_DB, uid, settings.ODOO_PASSWORD,
            "pos.order", "search_read",
            [[["date_order", ">=", f"{date} 00:00:00"],
              ["date_order", "<=", f"{date} 23:59:59"],
              ["config_id.name", "ilike", branch_name],
              ["state", "in", ["done", "paid"]]]],
            {"fields": ["name", "partner_id", "amount_total"], "limit": 200}
        )
        for o in pos_orders:
            items.append({
                "odoo_ref": o["name"],
                "customer_name": o["partner_id"][1] if o.get("partner_id") else "ลูกค้าทั่วไป",
                "sale_type": "pos",
                "odoo_amount": o.get("amount_total", 0)
            })

        # Cash invoice payments
        payments = mdl.execute_kw(
            settings.ODOO_DB, uid, settings.ODOO_PASSWORD,
            "account.payment", "search_read",
            [[["date", "=", date],
              ["payment_type", "=", "inbound"],
              ["journal_id.type", "=", "cash"],
              ["state", "=", "posted"]]],
            {"fields": ["name", "partner_id", "amount"], "limit": 200}
        )
        for p in payments:
            items.append({
                "odoo_ref": p["name"],
                "customer_name": p["partner_id"][1] if p.get("partner_id") else "-",
                "sale_type": "invoice",
                "odoo_amount": p.get("amount", 0)
            })

        return items
    except Exception as e:
        print(f"Odoo get_cash_sales error: {e}")
        return _fake_cash_sales(date, branch)


def _fake_cash_sales(date: str, branch: str) -> list:
    """รายการจำลองสำหรับ dev/demo"""
    import random
    seed = int(date.replace("-", "")) + (1 if branch == "rama3" else 2)
    rng = random.Random(seed)
    customers = ["บ.สยามเทค จก.", "ร.อรุณพาณิชย์", "คุณสมชาย", "คุณนภา", "ลูกค้าทั่วไป", "บ.กรีนแพค จก.", "คุณวิชัย", "ร.มงคลการค้า"]
    items = []
    n = rng.randint(4, 9)
    for i in range(n):
        sale_type = "pos" if rng.random() > 0.3 else "invoice"
        ref = f"POS/{date.replace('-','/')}/{1000+i}" if sale_type == "pos" else f"INV/{date.replace('-','/')}/{500+i}"
        items.append({
            "odoo_ref": ref,
            "customer_name": rng.choice(customers),
            "sale_type": sale_type,
            "odoo_amount": round(rng.uniform(500, 25000), 2)
        })
    return items


def _fake_odoo(date: str, branch: str) -> dict:
    """ข้อมูลจำลองสำหรับ dev/demo"""
    seed = int(date.replace("-", "")) + (1 if branch == "rama3" else 2)
    h = seed % 97
    pos = (h * 1237 + 8000) % 50000 + 5000
    inv = (h * 853 + 2000) % 20000
    exp = (h * 421 + 500) % 8000
    return {"pos": float(pos), "inv": float(inv), "exp": float(exp), "net": float(pos + inv - exp)}
