
import time
import typing

import slack_scim

import slacktivate.slack.clients
import slacktivate.slack.retry


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "lookup_user_by_id",
    "lookup_user_by_username",
    "lookup_user_by_email",

    "SlackUser",

    "to_slack_user",
]


def _escape_filter_param(s):
    if s is None:
        return ""
    return s.replace("'", "")


def _first_or_none(lst: typing.Optional[typing.List[typing.Any]]) -> typing.Any:
    if lst is None or len(lst) == 0:
        return
    return lst[0]


@slacktivate.slack.retry.slack_retry
def lookup_user_by_id(user_id: str) -> typing.Optional[slack_scim.User]:
    user_id = _escape_filter_param(user_id)

    try:
        result = slacktivate.slack.clients.scim().read_user(user_id)
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return result


@slacktivate.slack.retry.slack_retry
def lookup_user_by_username(username: str) -> typing.Optional[slack_scim.User]:
    username = _escape_filter_param(username)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_users(
            filter="username eq '{}'".format(username),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return _first_or_none(result)


@slacktivate.slack.retry.slack_retry
def lookup_user_by_email(email: str) -> typing.Optional[slack_scim.User]:
    email = _escape_filter_param(email)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_users(
            filter="email eq '{}'".format(email),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return _first_or_none(result)


class SlackUser:

    _user: typing.Optional[slack_scim.User] = None

    _provided_email: typing.Optional[str] = None
    _provided_username: typing.Optional[str] = None

    # *************************************

    def __init__(
            self,
            user_id: typing.Optional[str] = None,
            username: typing.Optional[str] = None,
            email: typing.Optional[str] = None,
            user: typing.Optional[slack_scim.User] = None,
    ):
        self._provided_username = username
        self._provided_email = email

        if user_id is not None:
            self._user = lookup_user_by_id(user_id=user_id)
        if username is not None:
            self._user = lookup_user_by_username(username=username)
        if email is not None:
            self._user = lookup_user_by_email(email=email)
        if user is not None:
            self._user = user

    def refresh(self):
        if self._user is not None:
            self._user = lookup_user_by_id(user_id=self._user.id)
            return True
        return False

    def __repr__(self):
        if self._user is not None:
            return "SlackUser[{id}, {userName}, {email}]".format(
                email=self._user.emails[0].value,
                **self._user.to_dict(),
            )

    # *************************************

    @classmethod
    def from_id(cls, user_id: str):
        return cls(user_id=user_id)

    @classmethod
    def from_username(cls, username: str):
        return cls(username=username)

    @classmethod
    def from_email(cls, email: str):
        return cls(email=email)

    @classmethod
    def from_user(cls, user: slack_scim.User):
        return cls(user=user)

    @classmethod
    def from_string(cls, string: str):
        # https://api.slack.com/changelog/2016-08-11-user-id-format-changes
        if string.isalnum() and string[:1].upper() in ["W", "U"]:
            return cls.from_id(user_id=string)

        if "@" in string and " " not in string:
            return cls.from_email(email=string)

        return cls.from_username(username=string)

    @classmethod
    def from_any(cls, value: typing.Union[str, slack_scim.User, None]):
        if value is None:
            return

        if isinstance(value, str):
            return cls.from_string(string=value)

        if isinstance(value, slack_scim.User):
            return cls.from_user(value)

    # *************************************

    @property
    def id(self):
        if self._user is not None:
            return self._user.id

    @property
    def username(self):
        if self._user is not None:
            return self._user.user_name

    @property
    def email(self):
        if self._user is not None:
            return self._user.emails[0].value

    # *************************************

    @property
    def exists(self):
        return self._user is not None

    @property
    def active(self):
        if not self.exists:
            return False

        return self._user.active


SlackUserTypes = typing.Union[str, slack_scim.User, SlackUser]


def to_slack_user(value: typing.Optional[SlackUserTypes]) -> typing.Optional[SlackUser]:
    if isinstance(value, SlackUser):
        return value

    return SlackUser.from_any(value=value)

