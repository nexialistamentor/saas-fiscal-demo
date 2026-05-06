def test_obter_meus_dados(client, auth_headers):
    response = client.get("/auth/my-data", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "empresas_registadas" in data
    assert "termos_aceites" in data
    assert "consentimentos_lgpd" in data


def test_eliminar_meus_dados(client, auth_headers):
    response = client.delete("/auth/my-data", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "dados pessoais anonimizados"
