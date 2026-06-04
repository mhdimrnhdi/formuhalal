import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/dist", StaticFiles(directory=Path(__file__).parent.parent / "dist"), name="dist")
app.mount("/assets", StaticFiles(directory=Path(__file__).parent.parent / "dist" / "assets"), name="assets")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
def landing(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/about")
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {})


@app.get("/terms")
def terms(request: Request):
    return templates.TemplateResponse(request, "terms.html", {})


@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@app.get("/formulation")
def formulation(request: Request):
    backend_url = os.getenv("PUBLIC_BACKEND_URL", "http://localhost:8001")
    return templates.TemplateResponse(request, "formulation.html", {"backend_url": backend_url})
