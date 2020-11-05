
"""
This submodule contains a number of high-level macros that assist
in complicated, multi-step tasks to be applied on Slack objects.
"""

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
    "UserMergeOptionsType",
    "UserMergeType",

    "user_access_logs",
    "user_access_count",
    "user_access_earliest",
    "user_access_latest",

    "user_merge",
]


class UserMergeOptionsType(enum.Enum):
    """
    Enumeration class of the different possibilities for merging user
    attributes in the :py:func:`user_merge` method.
    """

    KEEP_FROM = "keep-from"
    """Keep the attributes of the user specified as :py:data:`user_from`."""

    KEEP_TO = "keep-to"
    """Keep the attributes of the user specified as :py:data:`user_to`."""

    KEEP_MOST_FREQUENT_LOGIN = "most-freq-login"
    """Keep the attributes of the user that has *most frequently logged* into Slack."""

    KEEP_LEAST_FREQUENT_LOGIN = "least-freq-login"
    """Keep the attributes of the user that has *least frequently logged* into Slack."""

    KEEP_NEWEST = "newest"
    """Keep the attributes of the *most recently created* user account (in other words, the newest)."""

    KEEP_OLDEST = "oldest"
    """Keep the attributes of the *least recently created* user account (in other words, the oldest)."""

    KEEP_MOST_RECENTLY_ACCESSED = "most-recent"
    """Keep the attributes of the *most recently accessed* user account."""

    KEEP_LEAST_RECENTLY_ACCESSED = "least-recent"
    """Keep the attributes of the *least recently accessed* user account."""


UserMergeType = typing.Optional[typing.Union[str, UserMergeOptionsType]]
"""
This is a type to specify the different possibilities for merging user
attributes in the :py:func:`user_merge` method. The values can either be
taken from the enumeration class :py:class:`UserMergeOptionsType`, be a
string, or be `None` (in which case a default decision will be made).
"""


_access_logs: typing.Optional[typing.List[dict]] = None
"""
Internal accesss logs cache for the currently logged-in Slack workspace.
This cache is (re)loaded by :py:func:`_refresh_access_logs`, and is used
by the following methods:

   - :py:func:`user_access_logs`,
   - :py:func:`user_access_count`,
   - :py:func:`user_access_earliest`,
   - :py:func:`user_access_latest`,
   - :py:func:`user_merge`,

and possibly other, protected, methods.
"""


def _refresh_access_logs(force_refresh: typing.Optional[bool] = None) -> typing.NoReturn:
    """
    Loads the internal access logs cache for the currently logged-in
    Slack workspace. If the cache has already been loaded, this does
    nothing, unless the parameter :py:data:`force_refresh` is set to
    :py:data:`True`.

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool
    """
    global _access_logs
    if _access_logs is None or (force_refresh is not None and force_refresh):
        _access_logs = slacktivate.slack.methods.team_access_logs()


def user_access_logs(
        user: slacktivate.slack.classes.SlackUserTypes,
        force_refresh: typing.Optional[bool] = None,
) -> typing.Optional[typing.List[dict]]:
    """
    Returns a list of the access logs for the requested user.

    An individual access log entry can aggregate multiple events or
    represent a single event (this depends on the value of ``count``),
    for example, the following entry represents a single event::

        {
            "user_id": "UTZLJA2JK",
            "username": "lumbroso",
            "date_first": 1603940797,
            "date_last": 1603940797,
            "count": 1,
            "ip": "96.248.68.184",
            "user_agent": "ApiApp/A0104EA0FPD Python/3.8.5 slackclient/2.9.3 Darwin/19.6.0",
            "isp": "",
            "country": "",
            "region": ""
        }

    There is no way to access the logs randomly, therefore this method
    relies on a local cache of the full team access logs. This means that
    the first call to this method may take some time while the access logs
    are loaded using an internal call to
    :py:func:`slacktivate.slack.methods.team_access_logs`; and the data
    may be slightly out of date (a refresh of the data can be forced by
    setting :py:data:`force_refresh` to :py:data:`True`).

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: A list of all available access logs for the user
    """

    # load cache if it does not already exist
    _refresh_access_logs(force_refresh=force_refresh)

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
        user: slacktivate.slack.classes.SlackUserTypes,
        force_refresh: typing.Optional[bool] = None,
) -> int:
    """
    Returns the number of times the user logged into Slack.

    There is no way to access the logs randomly, therefore this method
    relies on a local cache of the full team access logs. This means that
    the first call to this method may take some time while the access logs
    are loaded using an internal call to
    :py:func:`slacktivate.slack.methods.team_access_logs`; and the data
    may be slightly out of date (a refresh of the data can be forced by
    setting :py:data:`force_refresh` to :py:data:`True`).

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: The total number of accesses a user has made
        (or -1 if user is not found)
    """

    # normalize user
    user = slacktivate.slack.classes.to_slack_user(user)
    user_logins = user_access_logs(user=user, force_refresh=force_refresh)
    if user is None or user_logins is None:
        return -1

    # process the logins to count total accesses
    total_accesses = 0
    for login in user_logins:
        total_accesses += login.get("count", 0)

    return total_accesses


def _user_access_numeric_field(
        user: slacktivate.slack.classes.SlackUserTypes,
        date_field_name: str,
        comparator: typing.Callable[[int, int], int] = operator.lt,
        force_refresh: typing.Optional[bool] = None,
) -> int:
    """
    Returns a numeric value (such as a count, or a Unix timestamp) computed
    over the Slack access logs for a given user. This helper method is used
    by :py:func:`user_access_earliest` and :py:func:`user_access_latest`.

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param date_field_name: The name of the field of the access logs that
        should be analyzed (e.g., ``date_first``, ``date_last``, ``count``)
    :type date_field_name: str

    :param comparator: A binary method to compare two values

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: The computed number
    """

    # normalize user
    user = slacktivate.slack.classes.to_slack_user(user)
    user_logins = user_access_logs(user=user, force_refresh=force_refresh)
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


def user_access_earliest(
        user: slacktivate.slack.classes.SlackUserTypes,
        force_refresh: typing.Optional[bool] = None,
) -> int:
    """
    Returns the user's *earliest* recorded login to the Slack workspace.

    Like the other methods related to access logs, such as
    :py:func:`user_access_logs`, this method relies on an internal
    cache that can be controlled with the parameter :py:data:`force_refresh`.

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: The Unix timestamp of the *earliest* recorded login for the user
    """

    return _user_access_numeric_field(
        user=user,
        date_field_name="date_first",
        comparator=operator.lt,
        force_refresh=force_refresh,
    )


def user_access_latest(
        user: slacktivate.slack.classes.SlackUserTypes,
        force_refresh: typing.Optional[bool] = None,
) -> int:
    """
    Returns the user's *most recently* recorded login to the Slack workspace.

    Like the other methods related to access logs, such as
    :py:func:`user_access_logs`, this method relies on an internal
    cache that can be controlled with the parameter :py:data:`force_refresh`.

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: The Unix timestamp of the *most recently* recorded login for the user
    """

    return _user_access_numeric_field(
        user=user,
        date_field_name="date_last",
        comparator=operator.gt,
        force_refresh=force_refresh,
    )


def user_merge(
        user_from: slacktivate.slack.classes.SlackUserTypes,
        user_to: slacktivate.slack.classes.SlackUserTypes,

        merge_account: UserMergeType = None,
        merge_username: UserMergeType = None,
        merge_primary_email: UserMergeType = None,

        force_refresh: typing.Optional[bool] = None,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    """
    Merges two Slack users into one, combining the attributes using a set of
    automated rules.

    :param user_from: A valid user
    :type user_from: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param user_to: Another valid user
    :type user_to: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param merge_account: Determines which account to keep;
        by default keep the *oldest*, :py:attr:`UserMergeOptionsType.KEEP_OLDEST`
    :type merge_account: :py:class:`UserMergeType`

    :param merge_username: Determines which username to keep;
        by default keep the *newest*, :py:attr:`UserMergeOptionsType.KEEP_NEWEST`
    :type merge_username: :py:class:`UserMergeType`

    :param merge_primary_email: Determines which primary email to keep;
        by default keep the *newest*, :py:attr:`UserMergeOptionsType.KEEP_NEWEST`
    :type merge_primary_email: :py:class:`UserMergeType`

    :param force_refresh: Flag determining whether to flush the cache
    :type force_refresh: bool

    :return: If successful, the merged user, otherwise :py:data:`None`
    """

    user_from = slacktivate.slack.classes.to_slack_user(user_from)
    user_to = slacktivate.slack.classes.to_slack_user(user_to)

    # simple cases

    if user_from is None:
        return user_to

    if user_to is None:
        return user_from

    # since we are making a lot of calls, if we want to refresh cache, only
    # need to do it once
    _refresh_access_logs(force_refresh=force_refresh)

    # merge case

    # NOTE: could reimplement this to merge N accounts, with sorting
    # and keys, and reverse (but not sure it's worth the trouble:
    # What's the use case?)

    user_from_count = user_access_count(user_from)
    user_from_earliest = user_access_earliest(user_from)
    user_from_latest = user_access_latest(user_from)
    user_to_count = user_access_count(user_to)
    user_to_earliest = user_access_earliest(user_to)
    user_to_latest = user_access_latest(user_to)

    user_mfl = user_from if user_from_count > user_to_count else user_to
    user_lfl = user_from if user_from_count < user_to_count else user_to
    user_new = user_from if user_from_earliest > user_to_earliest else user_to
    user_old = user_from if user_from_earliest < user_to_earliest else user_to
    user_mra = user_from if user_from_latest > user_to_latest else user_to
    user_lra = user_from if user_from_latest < user_to_latest else user_to

    def _select_user(
            flag: UserMergeOptionsType,
            default: UserMergeOptionsType = UserMergeOptionsType.KEEP_TO,
            reverse: bool = False,
    ) -> slacktivate.slack.classes.SlackUser:
        if flag is None:
            flag = default

        reverse_flag_table = {
            UserMergeOptionsType.KEEP_FROM:                     UserMergeOptionsType.KEEP_TO,
            UserMergeOptionsType.KEEP_TO:                       UserMergeOptionsType.KEEP_FROM,
            UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN:      UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN,
            UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN:     UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN,
            UserMergeOptionsType.KEEP_NEWEST:                   UserMergeOptionsType.KEEP_OLDEST,
            UserMergeOptionsType.KEEP_OLDEST:                   UserMergeOptionsType.KEEP_NEWEST,
            UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED:   UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED,
            UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED:  UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED,
        }

        if reverse:
            flag = reverse_flag_table.get(flag)

        translation_table = {
            UserMergeOptionsType.KEEP_FROM:                     user_from,
            UserMergeOptionsType.KEEP_TO:                       user_to,
            UserMergeOptionsType.KEEP_MOST_FREQUENT_LOGIN:      user_mfl,
            UserMergeOptionsType.KEEP_LEAST_FREQUENT_LOGIN:     user_lfl,
            UserMergeOptionsType.KEEP_NEWEST:                   user_new,
            UserMergeOptionsType.KEEP_OLDEST:                   user_old,
            UserMergeOptionsType.KEEP_MOST_RECENTLY_ACCESSED:   user_mra,
            UserMergeOptionsType.KEEP_LEAST_RECENTLY_ACCESSED:  user_lra,
        }

        return translation_table.get(flag)

    # determine the user account to keep, and the one to deactivate
    user_to_keep = _select_user(flag=merge_account, default=UserMergeOptionsType.KEEP_OLDEST)
    user_to_dump = _select_user(flag=merge_account, default=UserMergeOptionsType.KEEP_OLDEST, reverse=True)

    # determine the user account from which to take username
    user_for_naming = _select_user(flag=merge_username, default=UserMergeOptionsType.KEEP_NEWEST)

    # determine the user account for primary email, and other
    user_for_primary_email = _select_user(flag=merge_primary_email, default=UserMergeOptionsType.KEEP_NEWEST)
    user_for_other_email = _select_user(flag=merge_primary_email, default=UserMergeOptionsType.KEEP_NEWEST, reverse=True)

    # recombine emails and build payload (yes, messy, please submit PR or issue to improve!)

    up_emails = user_for_primary_email.scim_obj.to_dict().get("emails", list())
    uo_emails = user_for_other_email.scim_obj.to_dict().get("emails", list())
    emails = up_emails + uo_emails
    for i in range(len(emails)):
        if emails[i].get("value") == user_for_primary_email.email:
            emails[i]["primary"] = True
        else:
            emails[i]["primary"] = False

    def _get_name(user_dict, field_name=None):
        fields = ["displayName", "userName", "nickName"]
        if field_name is not None:
            fields = [field_name] + fields
        for field_name in fields:
            value = user_dict.get(field_name)
            if value is not None:
                return value

    # build payload of new user

    u4nd = user_for_naming.scim_obj.to_dict()
    u2kd_patch = {
        "active": True,
        "emails": emails,
        "displayName": _get_name(user_dict=u4nd, field_name="displayName"),
        "userName": _get_name(user_dict=u4nd, field_name="userName"),
        "nickName": _get_name(user_dict=u4nd, field_name="nickName"),
        "name": u4nd.get("name"),
    }

    # deactivate user

    u2dd = user_to_dump.scim_obj.to_dict()
    deactivated_name = "_{}".format(user_to_dump.id)
    u2dd_patch = {
        "active": False,
        "emails": [{"value": user_for_primary_email.email.replace("@", "+deactivated@"), "primary": True}],
        "displayName": deactivated_name,
        "userName": deactivated_name,
        "nickName": deactivated_name,
    }

    # actually run the operations! (yikes!!! :-)

    # first the user to deactivate, so that we don't have an email conflict
    slacktivate.slack.methods.user_patch(
        user=user_to_dump.id,
        changes=u2dd_patch,
    )

    result = slacktivate.slack.methods.user_patch(
        user=user_to_keep.id,
        changes=u2kd_patch,
    )

    return result

