import sqlite3
import time
import pytest
from giginsure import validators as V


@pytest.mark.parametrize("bad", ["worker_01' OR '1'='1", "a;DROP TABLE workers", "", "x" * 40])
def test_identifier_validator_rejects_injection(bad):
    with pytest.raises(V.ValidationError):
        V.validate_worker_id(bad)


def test_parameterised_query_neutralises_injection():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE workers(worker_id TEXT)"); db.execute("INSERT INTO workers VALUES ('worker_01')")
    rows = db.execute("SELECT * FROM workers WHERE worker_id=?", ("worker_01' OR '1'='1",)).fetchall()
    assert rows == [] and db.execute("SELECT COUNT(*) FROM workers").fetchone()[0] == 1


def test_invalid_persona_refused():
    with pytest.raises(V.ValidationError):
        V.validate_persona("health")


@pytest.mark.parametrize("upi,ok", [("ravi.k99@okaxis", True), ("no-at-sign", False), ("a@b", False)])
def test_upi_handle_validation(upi, ok):
    if ok:
        assert V.validate_upi(upi) == upi
    else:
        with pytest.raises(V.ValidationError):
            V.validate_upi(upi)


def test_token_valid_expired_and_tampered():
    t = V.sign_token("GW0001", ttl_s=60)
    assert V.verify_token(t) == "GW0001"
    assert V.verify_token(t, now=time.time() + 120) is None
    p, s = t.split(".")
    forged = V._b64(V._unb64(p).replace(b"GW0001", b"GW0002")) + "." + s
    assert V.verify_token(forged) is None
