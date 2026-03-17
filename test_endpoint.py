from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0ZUBlbXByZXNhLmNvbSIsImV4cCI6MTc3MzcwOTAxMX0.GyZLptxD1pc8ch7P71C76kYZF-Provv9zWKNRPp52SQ"

r = client.get(
    "/inteligencia/mapa-oportunidades/4",
    headers={"Authorization": f"Bearer {token}"}
)

print(r.status_code)
print(r.text)
