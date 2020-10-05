
import datetime
import enum
import operator
import typing

import slacktivate.helpers.photo
import slacktivate.input.helpers
import slacktivate.input.parsing
import slacktivate.slack.classes
import slacktivate.slack.methods


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "UserMergeType",

    "user_access_logs",
    "user_access_count",
    "user_access_earliest",

]


class UserMergeOptionsType(enum.Enum):
    KEEP_FROM = "keep-from"
    KEEP_TO = "keep-to"
    KEEP_MOST_FREQUENT_LOGIN = "most-freq-login"
    KEEP_LEAST_FREQUENT_LOGIN = "least-freq-login"
    KEEP_NEWEST = "newest"
    KEEP_OLDEST = "oldest"


UserMergeType = typing.Optional[typing.Union[str, UserMergeOptionsType]]


_access_logs: typing.Optional[typing.List[dict]] = None


def _refresh_access_logs(force_refresh: typing.Optional[bool] = None):
    global _access_logs
    if _access_logs is None or (force_refresh is not None and force_refresh):
        _access_logs = slacktivate.slack.methods.team_access_logs()


def user_access_logs(
        user: slacktivate.slack.classes.SlackUserTypes
) -> typing.Optional[typing.List[dict]]:

    # load cache if it does not already exist
    _refresh_access_logs()

    # normalize user
    user = slacktivate.slack.classes.to_slack_user(user)
    if user is None:
        return

    # retrieve user logins, either through cache or fresh query
    user_logins = None
    if _access_logs is not None:
        # let's use cache if available: shorter query time
        user_logins = list(filter(
            lambda log: log.get("user_id") == user.id,
            _access_logs
        ))
    else:
        user_logins = slacktivate.slack.methods.team_access_logs(user=user)

    return user_logins


def user_access_count(
        user: slacktivate.slack.classes.SlackUserTypes
) -> int:

    # normalize user
    user = slacktivate.slack.classes.to_slack_user(user)
    user_logins = user_access_logs(user=user)
    if user is None or user_logins is None:
        return -1

    # process the logins to count total accesses
    total_accesses = 0
    for login in user_logins:
        total_accesses += login.get("count", 0)

    return total_accesses


def _user_access_date_field(
        user: slacktivate.slack.classes.SlackUserTypes,
        date_field_name: str,
        comparator: typing.Callable[[int, int], int] = operator.lt,
) -> int:

    # normalize user
    user = slacktivate.slack.classes.to_slack_user(user)
    user_logins = user_access_logs(user=user)
    if user is None or user_logins is None:
        return -1

    # process the logins to count total accesses
    best_access = None
    for login in user_logins:
        date_field_value = login.get(date_field_name)
        if date_field_value is None:
            continue
        if best_access is None:
            best_access = date_field_value
            continue
        if comparator(date_field_value, best_access):
            best_access = date_field_value

    return best_access


def user_access_earliest(user: slacktivate.slack.classes.SlackUserTypes) -> int:
    return _user_access_date_field(
        user=user,
        date_field_name="date_first",
        comparator=operator.lt,
    )


def user_access_latest(user: slacktivate.slack.classes.SlackUserTypes) -> int:
    return _user_access_date_field(
        user=user,
        date_field_name="date_last",
        comparator=operator.gt,
    )


# def user_merge(
#         user_from: slacktivate.slack.classes.SlackUserTypes,
#         user_to: slacktivate.slack.classes.SlackUserTypes,
#
#         merge_account: UserMergeType = None,
#         merge_username: UserMergeType = None,
#         merge_primary_email: UserMergeType = None,
# ):
#     user_from = slacktivate.slack.classes.to_slack_user(user_from)
#     user_to = slacktivate.slack.classes.to_slack_user(user_to)
#
#     # simple cases
#     if user_from is None:
#         return user_to
#
#     if user_to is None:
#         return user_from
#
#     # merge case
#
#     if merge_type == UserMergeType.KEEP_TO:
#         # "normal" case: Do nothing
#         pass
#     elif merge_type == UserMergeType.KEEP_FROM:
#
#
#     elif merge_type == UserMergeType.KEEP_MOST_FREQUENT_LOGIN:
#         u_from_login_count = user_access_count(user=user_from)
#         u_to_login_count = user_access_count(user=user_to)
