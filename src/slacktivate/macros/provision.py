
import copy
import io
import typing

import slacktivate.input
import slacktivate.input.helpers
import slacktivate.input.parsing
import slacktivate.slack.methods


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
]


MAX_USER_LIMIT = 1000
SLACK_BOTS_DOMAIN = "@slack-bots.com"


_users_cache: typing.Optional[typing.Dict[str, slacktivate.slack.classes.SlackUser]] = None


def _refresh_users_cache() -> typing.NoReturn:
    global _users_cache

    result = slacktivate.slack.clients.scim().search_users(count=MAX_USER_LIMIT)

    # index by primary email
    _users_cache = {
        resource.emails[0].value.lower(): slacktivate.slack.classes.SlackUser(user=resource)
        for resource in result.resources
    }


def _lookup_slack_user_by_email(
        email: str
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

    if _users_cache is None:
        _refresh_users_cache()

    email = email.lower()

    result = _users_cache.get(email)

    return result


def _lookup_slack_user_id_by_email(
        email: str
) -> typing.Optional[str]:

    user = _lookup_slack_user_by_email(email=email)
    if user is not None:
        return user.id


def deactivate_users(
        config: slacktivate.input.SlacktivateConfig,
):

    # refresh the user cache
    _refresh_users_cache()

    # retrieve all the emails of the configured users in a list
    config_user_emails = [
        user.get("email", "").lower()
        for user in config.users.values()
    ]

    users_to_deactivate = []

    # iterate over all users currently on the Slack
    # => goal is to identify anybody not in the configuration
    for user_email, user in _users_cache.items():

        # check for exceptions, and skip them
        if SLACK_BOTS_DOMAIN in user_email:
            continue

        # if in the configuration file, user should be there, so skip
        if user_email in config_user_emails:
            continue

        # at this point, a user should not be in the Slack, and should
        # be deactivated
        users_to_deactivate.append(user)

    # now deactivate all at once
    for user in users_to_deactivate:
        slacktivate.slack.methods.user_deactivate(user)


def ensure_users(
        config: slacktivate.input.SlacktivateConfig,
):

    # refresh the user cache
    _refresh_users_cache()

    # get emails of cached users
    # NOTE: if needed to deal with alternate emails, would be here
    active_user_emails = [
        user_email
        for user_email in _users_cache.keys()
    ]

    users_to_create = {}

    # iterate over all users in config
    for user_email, user_attributes in config.users.items():

        # user already exists
        if user_email.lower() in active_user_emails:
            continue

        users_to_create[user_email] = user_attributes

    # create the users
    for user_email, user_attributes in users_to_create.items():
        pass

