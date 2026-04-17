import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.db import Base, InviteCode, User
from server.invites import (
    consume_invite,
    create_invite,
    hash_invite_code,
    register_user_with_invite,
    revoke_invite,
)


class InviteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.tmp.name) / 'invites.db'}")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def _admin(self, session):
        admin = User(username="admin", password_hash="x", role="admin", is_active=True)
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return admin

    def test_create_invite_stores_hash_not_plain_code(self):
        with self.Session() as session:
            admin = self._admin(session)

            result = create_invite(session, admin, max_uses=2, expires_hours=24)
            session.commit()

            row = session.query(InviteCode).one()
            self.assertEqual(row.code_hash, hash_invite_code(result["code"]))
            self.assertNotEqual(row.code_hash, result["code"])
            self.assertEqual(row.max_uses, 2)
            self.assertEqual(row.used_count, 0)
            self.assertIsNotNone(row.expires_at)

    def test_register_user_with_valid_invite_creates_regular_user_and_consumes_use(self):
        with self.Session() as session:
            admin = self._admin(session)
            invite = create_invite(session, admin, max_uses=1, expires_hours=None)

            user = register_user_with_invite(session, "alice", "abc123", invite["code"])
            session.commit()

            self.assertEqual(user.username, "alice")
            self.assertEqual(user.role, "user")
            row = session.query(InviteCode).one()
            self.assertEqual(row.used_count, 1)

    def test_invite_cannot_be_used_after_max_uses(self):
        with self.Session() as session:
            admin = self._admin(session)
            invite = create_invite(session, admin, max_uses=1, expires_hours=None)
            register_user_with_invite(session, "alice", "abc123", invite["code"])

            with self.assertRaises(HTTPException) as ctx:
                register_user_with_invite(session, "bob", "abc123", invite["code"])

            self.assertEqual(ctx.exception.status_code, 400)

    def test_revoked_invite_cannot_register(self):
        with self.Session() as session:
            admin = self._admin(session)
            invite = create_invite(session, admin, max_uses=1, expires_hours=None)
            revoke_invite(session, invite["id"])

            with self.assertRaises(HTTPException) as ctx:
                register_user_with_invite(session, "alice", "abc123", invite["code"])

            self.assertEqual(ctx.exception.status_code, 400)

    def test_expired_invite_cannot_register(self):
        with self.Session() as session:
            admin = self._admin(session)
            invite = create_invite(session, admin, max_uses=1, expires_hours=None)
            row = session.query(InviteCode).one()
            row.expires_at = datetime.now(UTC) - timedelta(hours=1)

            with self.assertRaises(HTTPException) as ctx:
                consume_invite(session, invite["code"])

            self.assertEqual(ctx.exception.status_code, 400)

    def test_register_rejects_duplicate_username_and_weak_input(self):
        with self.Session() as session:
            admin = self._admin(session)
            invite = create_invite(session, admin, max_uses=3, expires_hours=None)
            register_user_with_invite(session, "alice", "abc123", invite["code"])

            with self.assertRaises(HTTPException) as duplicate:
                register_user_with_invite(session, "alice", "abc123", invite["code"])
            self.assertEqual(duplicate.exception.status_code, 400)

            with self.assertRaises(HTTPException) as bad_username:
                register_user_with_invite(session, "ab", "abc123", invite["code"])
            self.assertEqual(bad_username.exception.status_code, 422)

            with self.assertRaises(HTTPException) as bad_password:
                register_user_with_invite(session, "charlie", "123", invite["code"])
            self.assertEqual(bad_password.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
