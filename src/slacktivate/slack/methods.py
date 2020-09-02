
import os
import typing

import slack
import slack_scim

import slacktivate.slack.classes
import slacktivate.slack.clients
import slacktivate.slack.retry


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "user_patch",

    "user_set_active",
    "user_activate",
    "user_deactivate",
]


@slacktivate.slack.retry.slack_retry
def user_patch(
        user: slacktivate.slack.classes.SlackUserTypes,
        changes: dict,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

    user = slacktivate.slack.classes.to_slack_user(user)
    if user is None:
        return

    result = slacktivate.slack.clients.scim().patch_user(
        id=user.id,
        user=changes,
    )

    if result is not None:
        return slacktivate.slack.classes.to_slack_user(result)


def user_set_active(
        user: slacktivate.slack.classes.SlackUserTypes,
        active: bool = True,
) -> bool:
    user = user_patch(
        user=user,
        changes={
            "active": active
        }
    )
    return user is not None and user.active == active


def user_activate(user: slacktivate.slack.classes.SlackUserTypes) -> bool:
    return user_set_active(user=user, active=True)


def user_deactivate(user: slacktivate.slack.classes.SlackUserTypes) -> bool:
    return user_set_active(user=user, active=False)

