from fastapi import FastAPI
from app.config import settings
from app.database import create_db_and_tables
from app.routers import auth, users, books, orders

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(orders.router)


@app.get("/")
def root():
    return {"message": "Welcome to Book Store API"}