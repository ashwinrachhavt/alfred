import importlib
import os


def test_pgbouncer_connect_args(monkeypatch):
    monkeypatch.setenv("DB_USE_PGBOUNCER", "true")
    monkeypatch.delenv("DB_SSL_CA_PATH", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    import alfred.core.config as cfg
    importlib.reload(cfg)
    from alfred.db import session as sess
    importlib.reload(sess)
    # When PgBouncer is enabled, prepared_statement_cache_size should be zero
    assert sess._pgbouncer_connect_args().get("prepared_statement_cache_size") == 0


def test_ssl_connect_args(monkeypatch, tmp_path):
    # Provide a fake CA path and stub ssl context creation to avoid real cert parsing
    cafile = tmp_path / "ca.crt"
    cafile.write_text("irrelevant-test")
    monkeypatch.setenv("DB_SSL_CA_PATH", str(cafile))
    monkeypatch.setenv("DB_USE_PGBOUNCER", "false")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )

    import ssl as _ssl
    class DummyCtx:
        check_hostname = True
        verify_mode = 0
    monkeypatch.setattr(_ssl, "create_default_context", lambda cafile=None: DummyCtx())

    import alfred.core.config as cfg
    importlib.reload(cfg)
    from alfred.db import session as sess
    importlib.reload(sess)
    # SSL context should be present in connect args
    assert "ssl" in sess._ssl_connect_args()
