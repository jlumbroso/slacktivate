
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
    KEEP_MOST_RECENTLY_ACCESSED = "most-recent"
    KEEP_LEAST_RECENTLY_ACCESSED = "least-recent"


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
#
#         username_field: typing.Optional[str] = None,
# ):
#     user_from = slacktivate.slack.classes.to_slack_user(user_from)
#     user_to = slacktivate.slack.classes.to_slack_user(user_to)
#
#     # simple cases
#
#     if user_from is None:
#         return user_to
#
#     if user_to is None:
#         return user_from
#
#     # merge case
#
#     # NOTE: could reimplement this to merge N accounts, with sorting
#     # and keys, and reverse (but not sure it's worth the trouble:
#     # What's the use case?)
#
#     user_from_count = user_access_count(user_from)
#     user_from_earliest = user_access_earliest(user_from)
#     user_from_latest = user_access_latest(user_from)
#     user_to_count = user_access_count(user_to)
#     user_to_earliest = user_access_earliest(user_to)
#     user_to_latest = user_access_latest(user_to)
#
#     user_mfl = user_from if user_from_count > user_to_count else user_to
#     user_lfl = user_from if user_from_count < user_to_count else user_to
#     user_new = user_from if user_from_earliest < user_to_earliest else user_to
#     user_old = user_from if user_from_earliest > user_to_earliest else user_to
#     user_mra = user_from if user_from_latest > user_to_latest else user_to
#     user_lra = user_from if user_from_latest < user_to_latest else user_to
#
#     def _select_user(
#             flag: UserMergeOptionsType,
#             default: UserMergeOptionsType = UserMergeOptionsType.KEEP_TO,
#             reverse: bool = False,
#     ) -> slacktivate.slack.classes.SlackUser:
#         if flag is None:
#             flag = default
#
#         reverse_flag_table = {
#             UserMergeOptionsType.KEEP_FROM:                     UserMergeOptionsType.KEEP_TO,
#             UserMergeOptionsType.KEEP_TO:                       UserMergeOptionsType.KEEP_FROM,
#             UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN:      UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN,
#             UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN:     UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN,
#             UserMergeOptionsType.KEEP_NEWEST:                   UserMergeOptionsType.KEEP_OLDEST,
#             UserMergeOptionsType.KEEP_OLDEST:                   UserMergeOptionsType.KEEP_NEWEST,
#             UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED:   UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED,
#             UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED:  UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED,
#         }
#
#         if reverse:
#             flag = reverse_flag_table.get(flag)
#
#         translation_table = {
#             UserMergeOptionsType.KEEP_FROM:                     user_from,
#             UserMergeOptionsType.KEEP_TO:                       user_to,
#             UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN:      user_mfl,
#             UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN:     user_lfl,
#             UserMergeOptionsType.KEEP_NEWEST:                   user_new,
#             UserMergeOptionsType.KEEP_OLDEST:                   user_old,
#             UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED:   user_mra,
#             UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED:  user_lra,
#         }
#
#         return translation_table.get(flag)
#
#     user_id = _select_user(flag=merge_account, default=UserMergeOptionsType.KEEP_TO).id
#
#     user_for_naming = _select_user(flag=merge_username, default=UserMergeOptionsType.KEEP_NEWEST)
#     user_for_primary_email = _select_user(flag=merge_primary_email, default=UserMergeOptionsType.KEEP_NEWEST)
#
#     u4nd = user_for_naming.scim_obj.to_dict()
#
#     user_dict = {
#         "name": u4nd.get("name"),
#         "displayName": u4nd.get("displayName"),
#         "nickName": u4nd.get("nickName"),
#         "nickName": u4nd.get("nickName"),
#     }
