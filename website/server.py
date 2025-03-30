from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes.livelog.livelog import livelog_router

app = FastAPI()

# Observice
app.include_router(livelog_router, prefix="/livelog", tags=["livelog"])
app.mount("/static", StaticFiles(directory="app/routes/static"), name="livelog_static")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Home Server app!"}
