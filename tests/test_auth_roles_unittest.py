import asyncio
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.auth import require_admin, verify_token
from server.db import AuthToken, Base, User
from server.models import CreateUserRequest, UpdateUserRequest


class AuthRoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.tmp.name) / 'auth.db'}")
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()

    def test_verify_token_returns_active_user(self):
        with self.Session() as session:
            user = User(username="alice", password_hash="x", role="user", is_active=True)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.add(
                AuthToken(
                    token="token-1",
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                )
            )
            session.commit()

            payload = verify_token(session, "token-1")

            self.assertIsNotNone(payload)
            self.assertEqual(payload["user_id"], user.id)
            self.assertEqual(payload["username"], "alice")
            self.assertEqual(payload["role"], "user")

    def test_require_admin_rejects_regular_user(self):
        user = User(username="bob", password_hash="x", role="user", is_active=True)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(require_admin(user))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_user_models_reject_readonly_role(self):
        with self.assertRaises(ValidationError):
            CreateUserRequest(username="viewer", password="secret", role="readonly")

        with self.assertRaises(ValidationError):
            UpdateUserRequest(role="readonly")


if __name__ == "__main__":
    unittest.main()
