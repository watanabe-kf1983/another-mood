"""Tests for the UserError base."""

from another_mood.components.shared.user_error import UserError


class TestUserError:
    def test_user_error_message_defaults_to_str(self) -> None:
        exc = UserError("run mood init first")
        assert exc.user_error_message == "run mood init first"
