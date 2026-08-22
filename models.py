from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    full_name       = Column(String(100))
    hashed_password = Column(String, nullable=False)
    is_admin        = Column(Boolean, default=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


class CashSaleItem(Base):
    """รายการขายเงินสดรายบิล (flow หลัก)"""
    __tablename__ = "cash_sale_items"
    id              = Column(Integer, primary_key=True, index=True)
    date            = Column(String(10), nullable=False)          # YYYY-MM-DD
    branch          = Column(String(20), nullable=False)          # rama3 | kaset
    odoo_ref        = Column(String(100))                         # POS/INV ref
    customer_name   = Column(String(200), default="")
    sale_type       = Column(String(50), default="pos")           # pos | invoice
    odoo_amount     = Column(Float, nullable=False)
    adjusted_amount = Column(Float, nullable=True)                # null = ใช้ยอด Odoo
    remark          = Column(Text, default="")
    status          = Column(String(20), default="confirmed")     # confirmed
    confirmed_by    = Column(String(50), nullable=True)
    confirmed_at    = Column(DateTime, nullable=True)
    deposit_id      = Column(Integer, ForeignKey("deposits.id"), nullable=True)
    deposit_date    = Column(String(10), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    deposit         = relationship("Deposit", back_populates="sale_items")


class Deposit(Base):
    __tablename__ = "deposits"
    id           = Column(Integer, primary_key=True, index=True)
    branch       = Column(String(20), nullable=False)
    deposit_date = Column(String(10), nullable=False)
    total_amount = Column(Float, default=0)
    status       = Column(String(20), default="done")
    note         = Column(Text, default="")
    created_by   = Column(String(50))
    created_at   = Column(DateTime, default=datetime.utcnow)
    sale_items   = relationship("CashSaleItem", back_populates="deposit")


# Kept for backwards-compat (not used in new flow)
class CashRecord(Base):
    __tablename__ = "cash_records"
    id           = Column(Integer, primary_key=True, index=True)
    date         = Column(String(10), nullable=False)
    branch       = Column(String(20), nullable=False)
    odoo_pos     = Column(Float, default=0)
    odoo_inv     = Column(Float, default=0)
    odoo_exp     = Column(Float, default=0)
    odoo_net     = Column(Float, default=0)
    counted      = Column(Float, nullable=False)
    diff         = Column(Float, default=0)
    remark       = Column(Text, default="")
    created_by   = Column(String(50))
    created_at   = Column(DateTime, default=datetime.utcnow)
