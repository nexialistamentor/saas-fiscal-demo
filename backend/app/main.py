from fastapi import FastAPI

app = FastAPI(title="API Fiscal SaaS")

@app.get("/")
def root():
    return {"message": "API Fiscal SaaS online"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
