
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


_custom_fields_by_label: typing.Optional[typing.Dict[str, dict]] = None


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
def user_create(
        attributes: typing.Dict[str, typing.Union[str, typing.Dict[str, str]]]
) -> slacktivate.slack.classes.SlackUser:

    with slacktivate.slack.clients.managed_scim() as scim:
        result = scim.create_user(
            user=attributes,
        )

    if result is not None:
        return slacktivate.slack.classes.to_slack_user(result)


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


def _refresh_custom_fields_cache() -> typing.NoReturn:
    global _custom_fields_by_label
    _custom_fields_by_label = list_custom_profile_fields()


def _make_user_extra_fields_dictionary(
        attributes: dict,
) -> typing.Dict[str, typing.Any]:

    # ensure we have the cache
    if _custom_fields_by_label is None:
        _refresh_custom_fields_cache()

    translated_extra_fields = {
        field_object.get("id"): {"value": attributes.get(label), "alt": ""}
        for (label, field_object) in _custom_fields_by_label.items()
    }

    return translated_extra_fields


def _make_user_dictionary(
        attributes,
        include_naming=True,
        include_image=True,
        include_fields=True,
):

    user_dict = {
        "emails": [{
            "primary": True,
            "type": None,
            "value": attributes.get("email"),
        }],
        "active": True,
    }

    if include_naming:
        user_name = attributes.get("userName")
        user_dict.update({
            "name": {
                "givenName": attributes.get("givenName"),
                "familyName": attributes.get("familyName"),
            },
            "userName": user_name,
            "displayName": user_name,
            "nickName": user_name,
        })

    if include_image:
        user_dict.update({
            "photos": {
                "value": attributes.get("image"),
                "primary": True,
            }
        })

    if include_fields:
        extra_fields_dict = _make_user_extra_fields_dictionary(
            attributes=attributes
        )

        user_dict.update({
            "fields": extra_fields_dict,
        })

    return user_dict


@slacktivate.slack.retry.slack_retry
def user_profile_set(
        user: slacktivate.slack.classes.SlackUserTypes,
        extra_fields: dict,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

    user = slacktivate.slack.classes.to_slack_user(user)
    if user is None:
        return

    with slacktivate.slack.clients.managed_api() as slack_client:
        result = slack_client.users_profile_set(
            user=user.id,
            profile={
                "fields": extra_fields
            },
        )

    if result is not None and result["ok"]:
        return result["profile"]
