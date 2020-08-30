
import time
import typing

import slack_scim
import slack_scim.v1.users

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


# =============================================================================


@slacktivate.slack.retry.slack_retry
def lookup_user_by_id(user_id: str) -> typing.Optional[slack_scim.User]:
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
        if user is not None and isinstance(user, slack_scim.User):
            self._user = user

    def refresh(self) -> bool:
        if self._user is not None:
            self._user = lookup_user_by_id(user_id=self._user.id)
            return True
        return False

    def __repr__(self) -> str:
        if self._user is not None:
            return "SlackUser[{id}, {userName}, {email}]".format(
                email=self._user.emails[0].value,
                **self._user.to_dict(),
            )
        return "SlackUser[undefined, {}, {}]".format(
            self._provided_username,
            self._provided_email,
        )

    # *************************************

    @classmethod
    def from_id(cls, user_id: str) -> "SlackUser":
        return cls(user_id=user_id)

    @classmethod
    def from_username(cls, username: str) -> "SlackUser":
        return cls(username=username)

    @classmethod
    def from_email(cls, email: str) -> "SlackUser":
        return cls(email=email)

    @classmethod
    def from_user(cls, user: slack_scim.User) -> "SlackUser":
        return cls(user=user)

    @classmethod
    def from_string(cls, string: str) -> "SlackUser":
        # https://api.slack.com/changelog/2016-08-11-user-id-format-changes
        if string.isalnum() and string[:1].upper() in ["W", "U"]:
            return cls.from_id(user_id=string)

        if "@" in string and " " not in string:
            return cls.from_email(email=string)

        return cls.from_username(username=string)

    @classmethod
    def from_any(
            cls,
            value: typing.Union[str, slack_scim.User, None]
    ) -> typing.Optional["SlackUser"]:
        if value is None:
            return

        if isinstance(value, str):
            return cls.from_string(string=value)

        if isinstance(value, slack_scim.User):
            return cls.from_user(value)

    # *************************************

    @property
    def id(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.id

    @property
    def username(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.user_name

    @property
    def email(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.emails[0].value

    # *************************************

    @property
    def exists(self) -> bool:
        return self._user is not None

    @property
    def active(self) -> bool:
        if not self.exists:
            return False

        return self._user.active


SlackUserTypes = typing.Union[str, slack_scim.User, SlackUser]


def to_slack_user(value: typing.Optional[SlackUserTypes]) -> typing.Optional[SlackUser]:
    if isinstance(value, SlackUser):
        return value

    return SlackUser.from_any(value=value)


# =============================================================================


@slacktivate.slack.retry.slack_retry
def lookup_group_by_id(group_id: str) -> typing.Optional[slack_scim.Group]:
    try:
        result = slacktivate.slack.clients.scim().read_group(group_id)
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return result


@slacktivate.slack.retry.slack_retry
def lookup_group_by_display_name(display_name: str) -> typing.Optional[slack_scim.Group]:
    display_name = _escape_filter_param(display_name)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_groups(
            filter="displayName eq '{}'".format(display_name),
            count=1,
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return _first_or_none(result)


class SlackGroup:

    _group: typing.Optional[slack_scim.Group] = None

    _provided_display_name: typing.Optional[str] = None

    # *************************************

    def __init__(
            self,
            group_id: typing.Optional[str] = None,
            display_name: typing.Optional[str] = None,
            group: typing.Optional[slack_scim.Group] = None,
    ):
        self._provided_display_name = display_name

        if group_id is not None:
            self._group = lookup_group_by_id(group_id=group_id)
        if display_name is not None:
            self._group = lookup_group_by_display_name(display_name=display_name)
        if group is not None and isinstance(group, slack_scim.Group):
            self._group = group

    def refresh(self) -> bool:
        if self._group is not None:
            self._group = lookup_group_by_id(group_id=self._group.id)
            return True
        return False

    def __repr__(self) -> str:
        if self._group is not None:
            return "SlackGroup[{id}, {displayName}]".format(
                **self._group.to_dict(),
            )
        return "SlackGroup[undefined, {}]".format(
            self._provided_display_name
        )

    # *************************************

    @classmethod
    def from_id(cls, group_id: str) -> "SlackGroup":
        return cls(group_id=group_id)

    @classmethod
    def from_display_name(cls, display_name: str) -> "SlackGroup":
        return cls(display_name=display_name)

    @classmethod
    def from_group(
            cls,
            group: typing.Union[slack_scim.Group, slack_scim.v1.users.Group]
    ) -> "SlackGroup":
        if isinstance(group, slack_scim.v1.users.Group):
            return cls(group_id=group.value)

        return cls(group=group)

    @classmethod
    def from_string(cls, string: str) -> "SlackGroup":

        # https://api.slack.com/types/usergroup
        if string.isalnum() and string[:1].upper() in ["S"]:
            try:
                group = lookup_group_by_id(group_id=string)
                return cls.from_group(group=group)
            except slack_scim.SCIMApiError:
                pass

        return cls.from_display_name(display_name=string)

    @classmethod
    def from_any(
            cls,
            value: typing.Union[str, slack_scim.Group, slack_scim.v1.users.Group, None]
    ) -> typing.Optional["SlackGroup"]:
        if value is None:
            return

        if isinstance(value, str):
            return cls.from_string(string=value)

        if isinstance(value, slack_scim.Group):
            return cls.from_group(group=value)

        if isinstance(value, slack_scim.v1.users.Group):
            return cls.from_group(group=value)


SlackGroupTypes = typing.Union[str, slack_scim.Group, slack_scim.v1.users.Group, SlackGroup]


def to_slack_group(
        value: typing.Optional[SlackGroupTypes]
) -> typing.Optional[SlackGroup]:
    if isinstance(value, SlackGroup):
        return value

    return SlackGroup.from_any(value=value)
