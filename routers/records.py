from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
import models
from auth import get_current_user
from odoo_client import get_odoo_cash

router = APIRouter(prefix="/api/records", tags=["records"])

class RecordCreate(BaseModel):
    date: str
    branch: str
    counted: float
    remark: Optional[str] = ""

class RecordOut(BaseModel):
    id: int
    date: str
    branch: str
    odoo_pos: float
    odoo_inv: float
    odoo_exp: float
    odoo_net: float
    counted: float
    diff: float
    remark: str
    deposit_id: Optional[int]
    deposit_date: Optional[str]
    created_by: str

    class Config:
        from_attributes = True

@router.get("/odoo")
def fetch_odoo(date: str = Query(...), branch: str = Query(...), _=Depends(get_current_user)):
    """ดึงยอดเงินสดจาก Odoo"""
    data = get_odoo_cash(date, branch)
    return data

@router.get("", response_model=List[RecordOut])
def list_records(
    branch: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    deposited: Optional[bool] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    q = db.query(models.CashRecord)
    if branch:
        q = q.filter(models.CashRecord.branch == branch)
    if date_from:
        q = q.filter(models.CashRecord.date >= date_from)
    if date_to:
        q = q.filter(models.CashRecord.date <= date_to)
    if deposited is True:
        q = q.filter(models.CashRecord.deposit_id.isnot(None))
    if deposited is False:
        q = q.filter(models.CashRecord.deposit_id.is_(None))
    return q.order_by(models.CashRecord.date.desc()).all()

@router.get("/{record_id}", response_model=RecordOut)
def get_record(record_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rec = db.query(models.CashRecord).filter(models.CashRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="ไม่พบรายการ")
    return rec

@router.post("", response_model=RecordOut)
def create_record(
    body: RecordCreate,
    db: Session = Depends(get_db),
    current=Depends(get_current_user)
):
    # Check duplicate
    dup = db.query(models.CashRecord).filter(
        models.CashRecord.date == body.date,
        models.CashRecord.branch == body.branch
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="มีรายการของสาขานี้วันนี้อยู่แล้ว")

    odoo = get_odoo_cash(body.date, body.branch)
    diff = body.counted - odoo["net"]

    rec = models.CashRecord(
        date=body.date,
        branch=body.branch,
        odoo_pos=odoo["pos"],
        odoo_inv=odoo["inv"],
        odoo_exp=odoo["exp"],
        odoo_net=odoo["net"],
        counted=body.counted,
        diff=diff,
        remark=body.remark or "",
        created_by=current.username
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
