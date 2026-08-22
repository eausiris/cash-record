from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
import models
from auth import get_current_user
from odoo_client import get_cash_sales, get_order_lines

router = APIRouter(prefix="/api/cash-sales", tags=["cash_sales"])


class SaleItemConfirm(BaseModel):
    odoo_ref: str
    customer_name: str
    sale_type: str
    odoo_amount: float
    adjusted_amount: Optional[float] = None
    remark: Optional[str] = ""


class BulkConfirm(BaseModel):
    date: str
    branch: str
    items: List[SaleItemConfirm]


class SaleItemOut(BaseModel):
    id: int
    date: str
    branch: str
    odoo_ref: str
    customer_name: str
    sale_type: str
    odoo_amount: float
    adjusted_amount: Optional[float]
    recorded_amount: float       # adjusted_amount ?? odoo_amount
    remark: str
    status: str
    confirmed_by: Optional[str]
    deposit_id: Optional[int]
    deposit_date: Optional[str]

    class Config:
        from_attributes = True


def to_out(s: models.CashSaleItem) -> SaleItemOut:
    rec = s.adjusted_amount if s.adjusted_amount is not None else s.odoo_amount
    return SaleItemOut(
        id=s.id, date=s.date, branch=s.branch,
        odoo_ref=s.odoo_ref, customer_name=s.customer_name, sale_type=s.sale_type,
        odoo_amount=s.odoo_amount, adjusted_amount=s.adjusted_amount,
        recorded_amount=rec, remark=s.remark or "",
        status=s.status, confirmed_by=s.confirmed_by,
        deposit_id=s.deposit_id, deposit_date=s.deposit_date,
    )


@router.get("/odoo-lines")
def fetch_order_lines(
    odoo_ref: str = Query(...),
    _=Depends(get_current_user),
):
    """ดึงรายการสินค้าในบิล POS"""
    return get_order_lines(odoo_ref)


@router.get("/odoo")
def fetch_from_odoo(
    date: str = Query(...),
    branch: str = Query(...),
    _=Depends(get_current_user),
):
    """ดึงรายการจาก Odoo สด (ยังไม่บันทึกลง DB)"""
    return get_cash_sales(date, branch)


@router.get("", response_model=List[SaleItemOut])
def list_confirmed(
    date: Optional[str] = None,
    branch: Optional[str] = None,
    deposited: Optional[str] = None,   # "true" | "false"
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.CashSaleItem)
    if date:
        q = q.filter(models.CashSaleItem.date == date)
    if branch:
        q = q.filter(models.CashSaleItem.branch == branch)
    if deposited == "false":
        q = q.filter(models.CashSaleItem.deposit_id.is_(None))
    elif deposited == "true":
        q = q.filter(models.CashSaleItem.deposit_id.isnot(None))
    items = q.order_by(models.CashSaleItem.date.desc(), models.CashSaleItem.id).all()
    return [to_out(s) for s in items]


@router.post("/confirm", response_model=List[SaleItemOut])
def confirm_items(
    body: BulkConfirm,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    now = datetime.utcnow()
    saved = []

    for item in body.items:
        has_adjustment = (
            item.adjusted_amount is not None
            and abs(item.adjusted_amount - item.odoo_amount) > 0.001
        )
        if has_adjustment and not (item.remark or "").strip():
            raise HTTPException(
                status_code=400,
                detail=f"รายการ {item.odoo_ref}: กรุณาระบุหมายเหตุเมื่อมีการแก้ไขยอด",
            )

        existing = (
            db.query(models.CashSaleItem)
            .filter(
                models.CashSaleItem.date == body.date,
                models.CashSaleItem.branch == body.branch,
                models.CashSaleItem.odoo_ref == item.odoo_ref,
            )
            .first()
        )

        if existing:
            # Don't allow re-confirming already-deposited items
            if existing.deposit_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"รายการ {item.odoo_ref} ถูกนำฝากไปแล้ว ไม่สามารถแก้ไขได้",
                )
            existing.adjusted_amount = item.adjusted_amount if has_adjustment else None
            existing.remark = item.remark or ""
            existing.status = "confirmed"
            existing.confirmed_by = current.username
            existing.confirmed_at = now
            db.flush()
            saved.append(existing)
        else:
            rec = models.CashSaleItem(
                date=body.date, branch=body.branch,
                odoo_ref=item.odoo_ref, customer_name=item.customer_name,
                sale_type=item.sale_type, odoo_amount=item.odoo_amount,
                adjusted_amount=item.adjusted_amount if has_adjustment else None,
                remark=item.remark or "",
                status="confirmed",
                confirmed_by=current.username,
                confirmed_at=now,
            )
            db.add(rec)
            db.flush()
            saved.append(rec)

    db.commit()
    for s in saved:
        db.refresh(s)
    return [to_out(s) for s in saved]
