import asyncio
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.api import change_my_password, update_my_profile
from server.auth import require_admin, verify_token
from server.db import AuthToken, Base, User, sync_admins_from_env
from server.models import ChangePasswordRequest, CreateUserRequest, UpdateProfileRequest, UpdateUserRequest


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
            self.assertEqual(payload["display_name"], "alice")
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

    def test_sync_admins_from_env_reactivates_existing_disabled_admin(self):
        with self.Session() as session:
            user = User(
                username="admin",
                password_hash="x",
                role="admin",
                is_active=False,
            )
            session.add(user)
            session.commit()

            sync_admins_from_env(
                session,
                [{"username": "admin", "password": "secret"}],
            )

            refreshed = session.query(User).filter(User.username == "admin").one()
            self.assertEqual(refreshed.role, "admin")
            self.assertTrue(refreshed.is_active)
            self.assertEqual(refreshed.display_name, "admin")
            self.assertEqual(refreshed.display_name_key, "admin")

    def test_sync_admins_from_env_promotes_and_reactivates_existing_user(self):
        with self.Session() as session:
            user = User(
                username="admin",
                password_hash="x",
                role="user",
                is_active=False,
            )
            session.add(user)
            session.commit()

            sync_admins_from_env(
                session,
                [{"username": "admin", "password": "secret"}],
            )

            refreshed = session.query(User).filter(User.username == "admin").one()
            self.assertEqual(refreshed.role, "admin")
            self.assertTrue(refreshed.is_active)
            self.assertEqual(refreshed.display_name, "admin")
            self.assertEqual(refreshed.display_name_key, "admin")

    def test_regular_user_can_update_profile_and_change_password(self):
        with self.Session() as session:
            user = User(username="alice", password_hash="x", role="user", is_active=True)
            session.add(user)
            session.commit()
            session.refresh(user)

            import bcrypt

            user.password_hash = bcrypt.hashpw("abc123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            session.add(
                AuthToken(
                    token="token-1",
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    is_active=True,
                )
            )
            session.commit()

            profile_result = asyncio.run(
                update_my_profile(
                    UpdateProfileRequest(display_name="星空旅人"),
                    current_user=user,
                    db=session,
                )
            )
            self.assertEqual(profile_result["user"]["display_name"], "星空旅人")

            password_result = asyncio.run(
                change_my_password(
                    ChangePasswordRequest(old_password="abc123", new_password="abc1234"),
                    current_user=user,
                    db=session,
                )
            )
            self.assertTrue(password_result["require_relogin"])
            active_tokens = session.query(AuthToken).filter(AuthToken.user_id == user.id, AuthToken.is_active == True).count()
            self.assertEqual(active_tokens, 0)


if __name__ == "__main__":
    unittest.main()
