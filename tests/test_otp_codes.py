"""One-time codes are stored and checked on the database clock."""


def _expiry_seconds(db, user_id):
    with db.get_connection() as conn:
        row = conn.execute(
            # No strftime("%s"): the query adapter reads %s as a placeholder.
            "SELECT CAST(ROUND((julianday(expires_at) - julianday('now')) * 86400) "
            "AS INTEGER) AS left_s "
            "FROM otp_codes WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        ).fetchone()
    return row["left_s"]


def test_code_lifetime_does_not_depend_on_server_timezone(app, registered_user):
    from app.extensions import get_db

    with app.app_context():
        db = get_db()
        user_id = db.get_user_by_username(registered_user["username"])["user_id"]
        db.store_otp(user_id, "135790", ttl_seconds=60)
        assert 55 <= _expiry_seconds(db, user_id) <= 61


def test_code_works_once(app, registered_user):
    from app.extensions import get_db

    with app.app_context():
        db = get_db()
        user_id = db.get_user_by_username(registered_user["username"])["user_id"]
        db.store_otp(user_id, "246801", ttl_seconds=60)
        assert db.verify_otp(user_id, "246801")
        assert not db.verify_otp(user_id, "246801")
