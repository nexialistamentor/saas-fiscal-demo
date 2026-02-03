from fastapi import FastAPI

app = FastAPI(title="SaaS Fiscal API")

@app.get("/")
def root():
    return {"message": "SaaS Fiscal API online"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
