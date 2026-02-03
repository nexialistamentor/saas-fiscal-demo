from fastapi import FastAPI

app = FastAPI(title="SaaS Fiscal API")

@app.get("/")
def root():
    return {
        "status": "online",
        "mensagem": "API SaaS Fiscal ativa"
    }

@app.get("/health")
def health():
    return {
        "status": "ok"
    }
