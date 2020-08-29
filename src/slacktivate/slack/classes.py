
import time
import typing

import slack_scim

import slacktivate.slack.clients


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "lookup_user_by_id",
    "lookup_user_by_username",
    "lookup_user_by_email",

    "SlackUser",

]



def _escape_filter_param(s):
    if s is None:
        return ""
    return s.replace("'", "")


def _first_or_none(lst: typing.Optional[typing.List[typing.Any]]) -> typing.Any:
    if lst is None or len(lst) == 0:
        return
    return lst[0]


def lookup_user_by_id(user_id: str) -> typing.Optional[slack_scim.User]:
    user_id = _escape_filter_param(user_id)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().read_user(user_id)
    except slack_scim.SCIMApiError as err:
        if err.status == 429:
            # handle rate limit errors
            time.sleep(1)
            return lookup_user_by_id(user_id)
        result = None

    return result


def lookup_user_by_username(username: str) -> typing.Optional[slack_scim.User]:
    username = _escape_filter_param(username)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_users(
            filter="username eq '{}'".format(username),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        if err.status == 429:
            # handle rate limit errors
            time.sleep(1)
            return lookup_user_by_username(username)
        result = []

    return _first_or_none(result)


def lookup_user_by_email(email: str) -> typing.Optional[slack_scim.User]:
    email = _escape_filter_param(email)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_users(
            filter="email eq '{}'".format(email),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        if err.status == 429:
            # handle rate limit errors
            time.sleep(1)
            return lookup_user_by_email(email)
        result = []

    return _first_or_none(result)




class SlackUser:

    def __init__(
            self,
            slack_id: typing.Optional[str] = None,
            username: typing.Optional[str] = None,
            email: typing.Optional[str] = None,
            user: typing.Optional[slack_scim.User] = None,
    ):
        if slack_id is not None:
            self._user = lookup_user_by_id(slack_id=slack_id)
        if username is not None:
            self._user = lookup_user_by_username(username=username)
        if email is not None:
            self._user = lookup_user_by_email(email=email)
        if user is not None:
            self._user = user

    def __repr__(self):
        if self._user is not None:
            print(self._user.to_dict())
            return "SlackUser[{id}, {userName}, {email}]".format(
                email=self._user.emails[0].value,
                **self._user.to_dict(),
            )

    @classmethod
    def from_id(cls, slack_id):
        return cls(slack_id=slack_id)

    @classmethod
    def from_username(cls, username):
        return cls(username=username)

    @classmethod
    def from_email(cls, email):
        return cls(email=email)

    @classmethod
    def from_user(cls, user):
        return cls(user=user)

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