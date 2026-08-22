from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
import models
from auth import get_current_user

router = APIRouter(prefix="/api/deposits", tags=["deposits"])


def make_doc_no(deposit_date: str, dep_id: int) -> str:
    d = deposit_date.replace("-", "")
    return f"DEP-{d}-{dep_id:03d}"


class DepositCreate(BaseModel):
    branch: str
    deposit_date: str
    sale_ids: List[int]
    note: Optional[str] = ""


class SaleItemBrief(BaseModel):
    id: int
    date: str
    odoo_ref: str
    customer_name: str
    sale_type: str
    odoo_amount: float
    adjusted_amount: Optional[float]
    remark: str

    class Config:
        from_attributes = True


class DepositOut(BaseModel):
    id: int
    doc_no: str
    branch: str
    deposit_date: str
    total_amount: float
    status: str
    note: str
    created_by: str
    sale_ids: List[int] = []

    class Config:
        from_attributes = True


def dep_to_out(dep: models.Deposit) -> DepositOut:
    return DepositOut(
        id=dep.id,
        doc_no=make_doc_no(dep.deposit_date, dep.id),
        branch=dep.branch,
        deposit_date=dep.deposit_date,
        total_amount=dep.total_amount,
        status=dep.status,
        note=dep.note or "",
        created_by=dep.created_by or "",
        sale_ids=[s.id for s in dep.sale_items],
    )


@router.get("", response_model=List[DepositOut])
def list_deposits(
    branch: Optional[str] = None,
    deposit_date: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.Deposit)
    if branch:
        q = q.filter(models.Deposit.branch == branch)
    if deposit_date:
        q = q.filter(models.Deposit.deposit_date == deposit_date)
    return [dep_to_out(d) for d in q.order_by(models.Deposit.deposit_date.desc()).all()]


@router.get("/{deposit_id}")
def get_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    dep = db.query(models.Deposit).filter(models.Deposit.id == deposit_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="ไม่พบรายการฝาก")
    items = dep.sale_items
    return {
        **dep_to_out(dep).dict(),
        "items": [
            {
                "id": s.id,
                "date": s.date,
                "odoo_ref": s.odoo_ref,
                "customer_name": s.customer_name,
                "sale_type": s.sale_type,
                "odoo_amount": s.odoo_amount,
                "recorded_amount": s.adjusted_amount if s.adjusted_amount is not None else s.odoo_amount,
                "remark": s.remark,
            }
            for s in items
        ],
    }


@router.post("", response_model=DepositOut)
def create_deposit(
    body: DepositCreate,
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    items = db.query(models.CashSaleItem).filter(
        models.CashSaleItem.id.in_(body.sale_ids)
    ).all()

    if len(items) != len(body.sale_ids):
        raise HTTPException(status_code=400, detail="ไม่พบรายการบางรายการ")
    for s in items:
        if s.deposit_id:
            raise HTTPException(
                status_code=400, detail=f"รายการ {s.odoo_ref} ถูกนำฝากไปแล้ว"
            )

    total = sum(
        (s.adjusted_amount if s.adjusted_amount is not None else s.odoo_amount)
        for s in items
    )

    dep = models.Deposit(
        branch=body.branch,
        deposit_date=body.deposit_date,
        total_amount=total,
        status="done",
        note=body.note or "",
        created_by=current.username,
    )
    db.add(dep)
    db.flush()

    for s in items:
        s.deposit_id = dep.id
        s.deposit_date = body.deposit_date

    db.commit()
    db.refresh(dep)
    return dep_to_out(dep)
