from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_partial_vienna_rent() -> None:
    res = client.post(
        "/query",
        json={"query": "I need average rent per square meter in Vienna districts 1 to 9 for the last 5 years"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "partial"


def test_geospatial_out_of_scope() -> None:
    res = client.post("/query", json={"query": "get Vienna district boundaries"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "no_data"
    assert any("unsupported_output_type" in item for item in body["metadata"]["limitations"])
