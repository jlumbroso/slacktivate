
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
    "user_create",
    "user_profile_set",
    "user_image_set",

    "make_user_dictionary",
    "make_user_extra_fields_dictionary",

    "group_create",
    "group_patch",
    "group_ensure",
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
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

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
            raise exc

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


def make_user_extra_fields_dictionary(
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


def make_user_dictionary(
        attributes,
        include_naming=True,
        include_image=True,
        include_fields=True,
):
    if attributes.get("email") is None:
        return

    user_name = attributes.get("userName")
    user_name = user_name or attributes.get("email").split("@")[0]

    user_dict = {
        "userName": user_name,
        "emails": [{
            "primary": True,
            "type": None,
            "value": attributes.get("email"),
        }],
        "active": True,
    }

    if include_naming:
        user_dict.update({
            "name": {
                "givenName": attributes.get("givenName"),
                "familyName": attributes.get("familyName"),
            },
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
        extra_fields_dict = make_user_extra_fields_dictionary(
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
                "fields": extra_fields,
            },
        )

    if result is not None and result["ok"]:
        return result["profile"]


def user_image_set(
        user: slacktivate.slack.classes.SlackUserTypes,
        image_url: str,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    user = user_patch(
        user=user,
        changes={
            "photos": {
                "value": image_url,
                "primary": True,
            }
        }
    )
    return user


@slacktivate.slack.retry.slack_retry
def group_create(
        display_name: str
) -> typing.Optional[slacktivate.slack.classes.SlackGroup]:

    grp = slacktivate.slack.classes.SlackGroup.from_display_name(
        display_name=display_name
    )

    if grp.exists:
        return grp

    with slacktivate.slack.clients.managed_scim() as scim:
        new_grp = slack_scim.Group.from_dict({
            "displayName": display_name
        })
        result = scim.create_group(group=new_grp)

    if result is not None:
        return slacktivate.slack.classes.to_slack_group(result)


@slacktivate.slack.retry.slack_retry
def group_patch(
        group: slacktivate.slack.classes.SlackGroupTypes,
        changes: dict,
) -> typing.Optional[slacktivate.slack.classes.SlackGroup]:

    group = slacktivate.slack.classes.to_slack_group(group)
    if group is None or not group.exists:
        return

    with slacktivate.slack.clients.managed_scim() as scim:
        scim.patch_group(
            id=group.id,
            group=changes,
        )

    result = slacktivate.slack.classes.SlackGroup.from_id(
        group_id=group.id)

    if result is not None:
        return result


def group_ensure(
        display_name: str,
        user_ids: typing.Optional[typing.List[str]] = None,
        remove_unspecified_members: bool = True,
):
    group = slacktivate.slack.classes.SlackGroup.from_display_name(
        display_name=display_name,
    )

    # ensure group exists
    if group is None or not group.exists:
        group = group_create(
            display_name=display_name,
        )
        if group is None:
            return

    # ensure membership
    current_member_ids = set() if group is None else set(group.member_ids)
    provided_member_ids = set() if user_ids is None else set(user_ids)

    # we may need to just extend the existing group (if remove_members is False)
    grp_member_ids = provided_member_ids
    grp_member_ids_to_delete = current_member_ids.difference(provided_member_ids)
    if remove_unspecified_members is not None and not remove_unspecified_members:
        grp_member_ids = provided_member_ids.union(current_member_ids)
        grp_member_ids_to_delete = set()

    # the {"operation": "delete"} is necessary to remove a member from a group in SCIM
    # http://www.simplecloud.info/specs/draft-scim-api-00.html#edit-resource-with-patch
    grp_members = {
        "members": list(map(
            lambda user_id: slack_scim.GroupMember.from_dict({
                "value": user_id,
            }),
            list(grp_member_ids)
        )) + list(map(
            lambda user_id: slack_scim.GroupMember.from_dict({
                "value": user_id,
                "operation": "delete"
            }),
            list(grp_member_ids_to_delete)
        ))
    }

    result = group_patch(
        group=group,
        changes=grp_members,
    )

    return result
