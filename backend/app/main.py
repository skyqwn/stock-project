from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stocks

app = FastAPI(title="KIS Stock Scaffold")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
