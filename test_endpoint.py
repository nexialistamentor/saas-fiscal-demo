from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0ZUBlbXByZXNhLmNvbSIsImV4cCI6MTc3MzY4NjEyN30.Yu4cmkw7Qy9HV7yDwy04qCP2fU1NJ6ej6c4r0-jn7Lw"

r = client.get(
    "/inteligencia/mapa-oportunidades/4",
    headers={"Authorization": f"Bearer {token}"}
)

print(r.status_code)
print(r.text)
