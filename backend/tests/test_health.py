from app.config import normalise_db_url


def test_health_reports_ok_and_reaches_the_database(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tests_run_against_the_test_database(session):
    name = session.connection().exec_driver_sql("SELECT current_database()").scalar()
    assert name.endswith("_test")


def test_cors_allows_the_web_app(client):
    r = client.options(
        "/health",
        headers={"Origin": "http://localhost:3100", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3100"


def test_hosted_postgres_urls_use_psycopg3():
    assert normalise_db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_db_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


def test_cors_allows_the_chrome_extension(client):
    origin = "chrome-extension://pjddbiflcebndfljpckcgkigckfpmndm"
    r = client.options(
        "/auth/me", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )
    assert r.headers.get("access-control-allow-origin") == origin
