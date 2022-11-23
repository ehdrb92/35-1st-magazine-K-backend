from datetime import datetime
import bcrypt
import jwt
import re

from django.conf import settings

from ..serializers import UserRepo
from user.utils.exceptions import (
    NotFoundError,
    NotFoundUserError,
    NotAuthorizedError,
    TokenExpiredError,
    EmailValidateError,
    PasswordValidateError,
)

user_repo = UserRepo()


class AuthProvider:
    def __init__(self):
        self.key = settings.SECRET_KEY
        self.expire_sec = settings.JWT_EXPIRE_TIME

    def _get_curr_sec(self):
        return datetime.now().timestamp()

    def hashpw(self, password: str):
        """
        해싱된 패스워드를 반환하는 함수
        """
        return bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode("utf8")

    def checkpw(self, password: str, hashed: str):
        return bcrypt.checkpw(password.encode("utf8"), hashed.encode("utf8"))

    def _decode(self, token: str):
        """
        전달받은 토큰을 디코딩하여 유효시간을 확인하는 함수
        """
        decoded = jwt.decode(token, self.key, algorithms=["HS256"])
        if decoded["exp"] <= self._get_curr_sec():
            raise TokenExpiredError
        else:
            return decoded

    def get_token_from_request(self, request):
        return request.META.get("HTTP_AUTHORIZATION", None)

    def create_token(self, user_id: str, is_expired: bool = False):
        """
        회원의 id값과 유효시간을 포함한 JWT를 생성하는 함수
        """
        exp = 0 if is_expired else self._get_curr_sec() + int(self.expire_sec)
        encoded_jwt = jwt.encode(
            {"id": user_id, "exp": exp},
            self.key,
            algorithm="HS256",
        )
        return encoded_jwt

    def validate_email(self, email):
        """
        기본적인 이메일 양식에 유효한지 확인하는 함수
        """
        REGEX_EMAIL = "^[a-zA-Z0-9+-_.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(REGEX_EMAIL, email):
            raise EmailValidateError

    def validate_password(self, password):
        """
        사이트의 비밀번호 양식에 유효한지 확인하는 함수

        비밀번호는 대소문자, 숫자, 특수문자를 반드시 포함하여 8~16자리의 수로 생성할 수 있습니다.
        """
        REGEX_PASSWORD = (
            "^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[~!@#$%^&*()])[A-Za-z\d~!@#$%^&*()]{8,16}"
        )
        if not re.match(REGEX_PASSWORD, password):
            raise PasswordValidateError

    def signup(
        self,
        email: str,
        password: str,
        name: str,
        phone_number: str,
    ) -> bool:
        self.validate_email(email=email)
        self.validate_password(password=password)
        hashpw = self.hashpw(password=password)
        created = user_repo.create_user(
            email=email,
            password=hashpw,
            name=name,
            phone_number=phone_number,
        )
        return created

    def signin(self, email: str, password: str):
        try:
            user = user_repo.get_user_by_email(email=email)
            if self.checkpw(password, user["password"]):
                return self.create_token(user["id"])
            else:
                raise NotFoundUserError()
        except Exception as e:
            if isinstance(e, NotFoundError):
                raise NotFoundUserError()
            else:
                raise e

    def signout(self, token: str):
        decoded = self._decode(token)
        return self.create_token(decoded["id"], is_expired=True)

    def check_auth(self, token: str) -> bool:
        """
        전달받은 토큰에서 유효시간과 id값을 확인하는 함수
        """
        decoded = self._decode(token)
        try:
            user = user_repo.get_user_by_id(decoded["id"])
            if user:
                return user
            else:
                raise NotAuthorizedError
        except Exception as e:
            if isinstance(e, NotFoundError):
                raise NotAuthorizedError
