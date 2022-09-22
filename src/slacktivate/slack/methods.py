
"""
This submodule provides an intermediate abstraction layer to the methods
provided by the Slack API and Slack SCIM API. This layer handles certain
errors (such as rate-limiting exceptions), uses the wrapper classes defined
in :py:mod:`slacktivate.slack.classes`, and provides a coherent,
predictable syntax to do typical, elementary administrative operations on
the logged-in Slack workspace.
"""

import itertools
import typing

import loguru
import slack
import slack.errors
import slack_scim

import slacktivate.helpers.collections
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
    "list_custom_profile_fields",
    "user_profile_set",
    "user_image_set",

    "make_user_dictionary",
    "make_user_extra_fields_dictionary",

    "group_create",
    "group_patch",
    "group_ensure",

    "channels_list",
    "channel_create",
    "conversation_member_ids",
    "team_access_logs",
]


MAX_PAGE_SIZE: int = 1000
"""
Internal maximal page size for API calls (see
`here <https://api.slack.com/changelog/2019-06-have-scim-will-paginate>`
for more information).
"""

_custom_fields_by_label: typing.Optional[typing.Dict[str, dict]] = None


logger = loguru.logger


@slacktivate.slack.retry.slack_retry
def user_patch(
        user: slacktivate.slack.classes.SlackUserTypes,
        changes: dict,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    """
    Patch an existing Slack user, as provided by the :py:data:`user` parameter,
    with modifications provided in the :py:data:`changes` parameter.

    .. seealso::
        See the `Slack SCIM API documentation <https://api.slack.com/scim#users>`_
        for an overview of the modifications that can be effected through this method
        with the dictionary passed through the :py:data:`changes` parameter.

    :param user: A valid user object
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param changes: A dictionary containing the changes to make
    :type changes: dict

    :return: The modified :py:class:`SlackUser` if successful,
        :py:data:`None` otherwise.
    """

    user = slacktivate.slack.classes.to_slack_user(user)
    if user is None:
        return

    result = None
    with slacktivate.slack.clients.managed_scim() as scim:
        try:
            result = scim.patch_user(
                id=user.id,
                user=changes,
            )
        except slack_scim.v1.errors.SCIMApiError as exc:
            logger.error(
                "Failed to patch user {user} with changes {changes}: {exc}",
                user=user,
                changes=changes,
                exc=exc,
            )

    if result is not None:
        return slacktivate.slack.classes.to_slack_user(result)


def user_set_active(
        user: slacktivate.slack.classes.SlackUserTypes,
        active: bool = True,
) -> bool:
    """
    Activates (or deactivates) an existing Slack user.

    :param user: A valid user object
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param active: Determines whether to make the user active
        (:py:data:`True`) or not (:py:data:`False`)

    :return: :py:data:`True` if the status of the user was successfully changed
    """

    user = user_patch(
        user=user,
        changes={
            "active": active,
        }
    )
    return user is not None and user.active == active


def user_activate(user: slacktivate.slack.classes.SlackUserTypes) -> bool:
    """
    Ensures an existing Slack user is active.

    :param user: A valid user object
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :return: :py:data:`True` if the status of the user is active
    """

    return user_set_active(user=user, active=True)


def user_deactivate(user: slacktivate.slack.classes.SlackUserTypes) -> bool:
    """
    Ensures an existing Slack user is deactivate.

    :param user: A valid user object
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :return: :py:data:`True` if the status of the user is active
    """

    return user_set_active(user=user, active=False)


@slacktivate.slack.retry.slack_retry
def user_create(
        attributes: typing.Dict[str, typing.Union[str, typing.Dict[str, str]]]
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    """
    Creates a new Slack user, based on the provided :py:data:`attributes`,
    using Slack SCIM API provisioning.

    .. note::
        Only the :py:data:`userName` and :py:data:`emails` attributes are
        `required to create a user <https://api.slack.com/scim#scim-api-endpoints__users>`_.

    :param attributes: A (possibly nested) dictionary containing the attributes
        for the user to be created
    :type attributes: dict

    :return: A valid Slack user, if successful
    """

    # required_fields_present = (
    #     attributes is not None and
    #     "userName" in attributes and
    #     "emails" in attributes
    # )

    result = None
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
    """
    Returns a dictionary of all the custom profile fields defined in the
    currently logged-in Slack workspace (custom fields are only available
    in Slack Plus and above plans).

    By default, the dictionary is indexed by the fields internal ID::

        {
            'Xf01AVK94ASU': {
                'id': 'Xf01AVK94ASU',
                'ordering': 0,
                'field_name': None,
                'label': 'Pronouns',
                'hint': 'E.g.: she/her/hers, he/him/his, they/them/theirs, ze/zim/zirs, ...',
                'type': 'text',
                'possible_values': None,
                'options': None,
                'is_hidden': False
            }
            ...
        }

    For more information, see `Slack's documentation of the API method
    <https://api.slack.com/methods/team.profile.get>`_.

    :param index_by_label: Flag to indicate whether the returned dictionary
        should be indexed by the label, rather than the ID
    :type index_by_label: bool

    :param silent_error: Flag to indicate whether to silently suppress any
        unexpected error and return an empty dictionary in that case
    :type silent_error: bool

    :raises: If :py:data:`silent_error` is :py:data:`False`, may raise a
        :py:exc:`slack.errors.SlackApiError`

    :return: The dictionary mapping a field ID to the internal dictionary
        defining a custom Slack profile field
    """

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


def _refresh_custom_fields_cache(silent_error: bool = True) -> typing.NoReturn:
    """
    Updates the internal cache of the logged-in Slack workspace's
    custom fields definition.
    """
    global _custom_fields_by_label
    _custom_fields_by_label = list_custom_profile_fields(
        index_by_label=True,
        silent_error=silent_error,
    )


def make_user_extra_fields_dictionary(
        attributes: dict,
) -> typing.Dict[str, typing.Any]:
    """
    Returns the payload to update a Slack user's customized profile fields; this
    is an internal method, that is only useful to make calls directly to the
    Slack API client.

    This method expects to provided a dictionary :py:data:`attributes`, mapping
    the customized fields to the their value, such as::

        {
            "Degree": "Ph.D.",
            "GitHub": "https://github.com/jlumbroso/",
        }

    Internally, a cache is maintained containing the result of a call to
    :py:func:`list_custom_profile_fields`, which allows this payload to be
    built by translating the labels into their corresponding field IDs.

    The resulting payload might be::

        {
            "Xf01957FNX4N": { "value": "Ph.D.", "alt":"" },
            "Xf019AHU8MJ9": { "value": "https://github.com/jlumbroso/", "alt":"" },
        }

    :param attributes: A dictionary mapping the profile customized fields to
        their content for a given user

    :return: A dictionary representing the payload to update a Slack user's
        customized profile fields
    """

    # ensure we have the cache
    if _custom_fields_by_label is None:
        _refresh_custom_fields_cache()

    translated_extra_fields = {
        field_object.get("id"): {"value": attributes.get(label), "alt": ""}
        for (label, field_object) in _custom_fields_by_label.items()
    }

    return translated_extra_fields


def _make_email_dictionary(
        email: typing.Union[dict, str],
        primary: typing.Optional[bool] = None,
        description: typing.Optional[str] = None,
) -> typing.Optional[dict]:
    # ensure values like this:
    # {
    #     "primary": True,
    #     "type": None,
    #     "value": "email@domain.com",
    # }

    # set default value for `primary`
    primary = primary if primary is not None else True

    if isinstance(email, str) and "@" in email:
        return {
            "primary": primary,
            "type": description,
            "value": email,
        }

    elif isinstance(email, dict) and "value" in email:
        return {
            "primary": email.get("primary", primary),
            "type": email.get("type", description),
            "value": email.get("value"),
        }

    # couldn't figure out email
    return


def _get_email_list(data: typing.Optional[typing.Union[str, list, dict]]) -> typing.List[str]:
    if data is None:
        return []

    if isinstance(data, str):
        return [data]

    if isinstance(data, dict) and "value" in data:
        return [data.get("value")]

    if isinstance(data, list):
        return list(itertools.chain(*map(_get_email_list, data)))

    return []


def make_user_email_dictionary(
        attributes: typing.Optional[dict] = None,
        primary_email: typing.Optional[str] = None,
        alternate_emails: typing.Optional[typing.Union[str, list]] = None,
):

    # MEA CULPA: Yes, this is some of the ugliest code I've ever written in
    # my life. -_-

    all_possible_emails = []

    # process email from `primary_email`
    if primary_email is not None:
        temp_lst = _get_email_list(data=primary_email)
        temp_email = slacktivate.helpers.collections.first_or_none(temp_lst)
        if temp_email is not None:
            all_possible_emails.append(temp_email)

    # process the emails from `attributes`
    if attributes is not None and ("email" in attributes or "emails" in attributes):
        # email_obj ~ {
        #     "primary": True,
        #     "type": None,
        #     "value": "email@domain.com",
        # }
        it = []

        if "email" in attributes and isinstance(attributes.get("email"), str):
            it.append(attributes.get("email"))
            if primary_email is None:
                primary_email = attributes.get("email")

        if "emails" in attributes and isinstance(attributes.get("emails"), list):
            it += attributes.get("emails")

        for obj in it:
            if isinstance(obj, dict) and "value" in obj:
                if "primary" in obj and obj["primary"]:
                    if primary_email is None:
                        primary_email = obj["value"]
                all_possible_emails.append(obj["value"])

            elif isinstance(obj, str):
                all_possible_emails.append(obj)

    # process the emails from `alternate_emails`
    alternate_emails = alternate_emails or attributes.get("alternate_emails")
    if alternate_emails is not None:
        all_possible_emails += _get_email_list(data=alternate_emails)

    # filter duplicates
    all_possible_emails = list(set(all_possible_emails))
    if primary_email is not None and primary_email in all_possible_emails:
        del all_possible_emails[all_possible_emails.index(primary_email)]

    ret = list(map(lambda email: _make_email_dictionary(email=email, primary=False),
                   all_possible_emails))

    if primary_email is not None:
        ret = [_make_email_dictionary(email=primary_email, primary=True)] + ret

    return ret


def make_user_dictionary(
        attributes: dict,
        include_naming: bool = True,
        include_image: bool = True,
        include_fields: bool = True,
) -> typing.Optional[dict]:
    """
    Returns the payload to update a Slack user's profile; this is an internal
    method, that is only useful to make calls directly to the Slack API client.

    :param attributes: A dictionary mapping the profile customized fields to
        their content for a given user

    :param include_naming: Flag determining whether to include the naming
        attributes (such as ``name``, ``displayName``, ``nickName``)

    :param include_image: Flag determining whether to include the profile image

    :param include_fields: Flag determining whether to include customized
        profile fields (as processed by the method
        :py:func:`make_user_extra_fields_dictionary`)

    :return: A dictionary representing the payload to update a Slack user's
        profile
    """

    if attributes.get("email") is None or type(attributes.get("email")) not in [str, list]:
        return

    user_name = attributes.get("userName")
    user_name = user_name or attributes.get("email").split("@")[0]

    user_email_dictionary = make_user_email_dictionary(
        attributes=attributes,
        primary_email=attributes.get("email"),
        alternate_emails=attributes.get("alternate_emails"),
    )

    user_dict = {
        "userName": user_name,
        "emails": user_email_dictionary,
        "active": True,
    }

    # support for alternate emails

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
    """
    Updates a Slack user's customized profile fields.

    :param user: A valid Slack user
    :type user: :py:class:`slacktivate.slack.classes.SlackUserTypes`

    :param extra_fields: A dictionary mapping customized profile
        fields to update, to their new values

    :type extra_fields: dict

    :return:
    """

    user = slacktivate.slack.classes.to_slack_user(user)
    if user is None:
        return

    result = None
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

    result = None
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


@slacktivate.slack.retry.slack_retry
def channels_list(
        by_id: bool = False,
        only_name: bool = False,
) -> typing.Optional[typing.Dict[str, typing.Dict[str, typing.Any]]]:

    with slacktivate.slack.clients.managed_api() as client:
        response = client.conversations_list(
            types="public_channel,private_channel"
        )

    # retrieve channels data
    channels_data = response.data.get("channels")
    if channels_data is None:
        return

    key = "name"
    other_key = "id"
    if by_id:
        (key, other_key) = (other_key, key)

    channels_by_key = {
        row[key]: row[other_key] if only_name else row
        for row in channels_data
    }

    return channels_by_key


@slacktivate.slack.retry.slack_retry
def channel_create(
        name: str,
        is_private: bool = False,
        return_id: bool = True,
) -> typing.Optional[typing.Union[str, typing.Dict[str, typing.Any]]]:

    with slacktivate.slack.clients.managed_api() as client:
        response = client.conversations_create(
            name=name,
            is_private=is_private,
        )

    if response.status_code < 300:
        channel_data = response.data.get("channels")
        return channel_data.get("id") if return_id else channel_data


@slacktivate.slack.retry.slack_retry
def conversation_member_ids(
        conversation_id: str,
) -> typing.List[str]:

    with slacktivate.slack.clients.managed_api() as client:
        response = client.conversations_members(
            channel=conversation_id,
        )

    # retrieve channel's members
    member_ids_list = response.data.get("members")

    return member_ids_list


@slacktivate.slack.retry.slack_retry
def team_access_logs(
        before: typing.Optional[int] = None,
        count: typing.Optional[int] = None,
        user: typing.Optional[slacktivate.slack.classes.SlackGroupTypes] = None,
        users: typing.Optional[typing.List[slacktivate.slack.classes.SlackGroupTypes]] = None,
        page_shifting: bool = True,
):
    # preprocess users

    user_filter = None

    if user is not None and users is not None:
        users = users + [user]
    elif user is not None and users is None:
        users = [user]

    if users is not None:
        users = map(slacktivate.slack.classes.to_slack_user, users)
        user_filter = list(map(lambda u: u.id, users))

    # gather logs
    agg_logs = []

    page = 1

    req_count = MAX_PAGE_SIZE
    if count is not None and count < MAX_PAGE_SIZE:
        req_count = count

    # needed to circumvent a Slack API limitation to 100 pages
    page_shift = 0

    while True:
        with slacktivate.slack.clients.managed_api() as client:
            result = client.team_accessLogs(
                before=before,
                count=req_count,
                page=page - page_shift,
            )

        # retry
        if result is None:
            continue

        # retrieve logins
        data = result.get("logins", list())

        if data is None or len(data) == 0:
            # if there's nothing left to read exit loop
            break

        # if only interested in records from specific users only keep those
        # results
        if user_filter is not None:
            data = list(filter(lambda login: login["user_id"] in user_filter, data))

        agg_logs += data

        # if we've retrieved as many records as we wanted, exist
        if count is not None and len(agg_logs) > count:
            break

        # next page!
        page += 1

        # Slack has a limititaton to 100 pages (even if there are more
        # available!!! hacks :-)
        if page % 100 == 1:

            # this flag limits how much data we pull
            if not page_shifting:
                break

            page_shift += 100

            # earliest date of the last data collected which is in
            # reverse chronological order, from newest to oldest so
            # we are looking for all events before the earliest one
            # we have collected

            before = data[-1]["date_first"] - 1

    return agg_logs[:count]


