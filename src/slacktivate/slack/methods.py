
import os
import typing

import slack
import slack.errors
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

    with slacktivate.slack.clients.managed_scim() as scim:
        result = scim.patch_user(
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


@slacktivate.slack.retry.slack_retry
def list_custom_profile_fields(
        index_by_label: bool = False,
        silent_error: bool = True,
) -> typing.Dict[str, str]:

    # https://api.slack.com/methods/team.profile.get
    try:
        # this will handle standard errors
        with slacktivate.slack.clients.managed_api() as api:
            response = api.team_profile_get()

        if not response.data["ok"]:
            raise slack.errors.SlackApiError(
                message="response failed",
                response=response)

    except slack.errors.SlackApiError as exc:
        if silent_error:
            # empty dictionary
            return dict()
        else:
            raise

    profile_fields = response.data.get("profile", dict()).get("fields")
    if profile_fields is None:
        if silent_error:
            # empty dictionary
            return dict()
        else:
            raise Exception("cannot find expected fields in response (`$.profile.fields`)")

    index = "label" if index_by_label else "id"
    indexed_fields = {
        field[index]: field
        for field in profile_fields
    }

    return indexed_fields
