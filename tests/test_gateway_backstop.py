"""Gateway gaps found in review.

The regex gateway blocked writes but had no view allowlist, so base tables
and the schema table were readable, and a caller-supplied LIMIT skipped the
100-row cap. Both are now enforced (authorizer + fetch cap).
"""
import pytest

from telcoops import telemetry, views


@pytest.fixture()
def conn():
    c = telemetry.build_db()
    views.create_views(c)
    yield c
    c.close()


@pytest.mark.parametrize("sql", [
    "SELECT * FROM techs",
    "SELECT name FROM sqlite_master",
    'SELECT * FROM v_open_incidents, "alarms"',
    "SELECT * FROM/**/incidents",
])
def test_non_view_reads_are_denied(conn, sql):
    with pytest.raises(views.GatewayError, match=r"SEC-SELECT-04"):
        views.run_query(conn, sql)


def test_caller_limit_cannot_exceed_cap(conn):
    _cols, rows = views.run_query(
        conn, "SELECT * FROM v_alarm_backlog a, v_tech_utilization b, v_open_incidents c LIMIT 100000")
    assert len(rows) <= views.MAX_LIMIT


def test_authorizer_is_removed_after_the_query(conn):
    views.run_query(conn, "SELECT * FROM v_open_incidents")
    assert conn.execute("SELECT count(*) FROM alarms").fetchone()[0] > 0
