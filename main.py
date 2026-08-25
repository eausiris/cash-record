from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from database import engine, Base
import models
from routers import auth, users, deposits, cash_sales
from auth import hash_password
from database import SessionLocal

app = FastAPI(title="Cash Record API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(deposits.router)
app.include_router(cash_sales.router)

# Serve frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(str(static_dir / "index.html"))


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # migrate: add slip_image column if not exists
    try:
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text(
                "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS slip_image TEXT"
            ))
            conn.commit()
    except Exception as e:
        print(f"Migration slip_image: {e}")
    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin:
            db.add(models.User(
                username="admin",
                full_name="Administrator",
                hashed_password=hash_password("admin1234"),
                is_admin=True,
            ))
            db.commit()
            print("✅ Created default admin: admin / admin1234")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
