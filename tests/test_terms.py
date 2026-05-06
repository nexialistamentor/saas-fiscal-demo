def test_has_accepted_terms_false(client, test_user, auth_headers):
    response = client.get("/auth/has-accepted-terms", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["accepted"] == False


def test_accept_terms(client, auth_headers):
    response = client.post("/auth/accept-terms", headers=auth_headers)
    assert response.status_code == 200
    response = client.get("/auth/has-accepted-terms", headers=auth_headers)
    assert response.json()["accepted"] is True
