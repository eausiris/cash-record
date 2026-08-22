# วิธี Deploy บน Railway

## ขั้นตอนที่ 1 — อัปโหลดโค้ดขึ้น GitHub

1. ไปที่ https://github.com → New repository → ชื่อ `cash-record` → Create
2. ในโฟลเดอร์ `cash-record/` เปิด Terminal แล้วรัน:

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/cash-record.git
git push -u origin main
```

## ขั้นตอนที่ 2 — สร้าง Project บน Railway

1. ไปที่ https://railway.app → Login ด้วย GitHub
2. กด **New Project** → **Deploy from GitHub repo** → เลือก `cash-record`
3. Railway จะ detect Dockerfile อัตโนมัติ กด **Deploy**

## ขั้นตอนที่ 3 — เพิ่ม PostgreSQL

1. ใน Project → กด **+ New** → **Database** → **PostgreSQL**
2. Railway จะสร้าง database และเพิ่ม `DATABASE_URL` ให้อัตโนมัติ

## ขั้นตอนที่ 4 — ตั้งค่า Environment Variables

ไปที่ **Service → Variables** แล้วเพิ่ม:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | ค่าสุ่ม เช่น `abc123xyz789...` (ยาวๆ) |
| `ODOO_URL` | `https://your-odoo.com` (ถ้ามี) |
| `ODOO_DB` | ชื่อ database Odoo |
| `ODOO_USER` | อีเมล Odoo |
| `ODOO_PASSWORD` | รหัสผ่าน Odoo |

> `DATABASE_URL` Railway เพิ่มให้อัตโนมัติแล้ว ไม่ต้องใส่เอง

## ขั้นตอนที่ 5 — เปิดใช้งาน

1. ไปที่ **Settings → Networking → Generate Domain**
2. Railway จะให้ URL เช่น `cash-record.up.railway.app`
3. เปิด URL นั้นในเบราว์เซอร์

## Login ครั้งแรก

```
username: admin
password: admin1234
```

**⚠️ เปลี่ยนรหัสผ่านทันทีหลัง login ครั้งแรก**

ไปที่แท็บ **จัดการผู้ใช้** → แก้ไข admin → ใส่รหัสผ่านใหม่

## เพิ่ม/ลบ User

ทำได้จากแท็บ **⚙️ จัดการผู้ใช้** (เฉพาะ Admin เท่านั้น)
