
import typing

import slacktivate.helpers.photo
import slacktivate.input.helpers
import slacktivate.input.parsing
import slacktivate.slack.classes
import slacktivate.slack.methods


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "users_deactivate",
    "users_ensure",
    "users_update",
]


MAX_USER_LIMIT = 1000
SLACK_BOTS_DOMAIN = "@slack-bots.com"


_users_cache_by_email: typing.Optional[typing.Dict[str, slacktivate.slack.classes.SlackUser]] = None
_users_cache_by_id: typing.Optional[typing.Dict[str, slacktivate.slack.classes.SlackUser]] = None


def _refresh_users_cache() -> typing.NoReturn:
    global _users_cache_by_email, _users_cache_by_id

    result = slacktivate.slack.clients.scim().search_users(count=MAX_USER_LIMIT)

    _users_cache_by_email = dict()
    _users_cache_by_id = dict()

    for resource in result.resources:

        # create wrapper around user
        user = slacktivate.slack.classes.SlackUser(resource=resource)
        if user is None or not user.exists:
            continue

        # index by primary email
        _users_cache_by_email[user.email] = user

        # index by id
        _users_cache_by_id[user.id] = user


def _lookup_slack_user_by_email(
        email: str
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

    if _users_cache_by_email is None:
        _refresh_users_cache()

    email = email.lower()

    result = _users_cache_by_email.get(email)

    return result


def _lookup_slack_user_id_by_email(
        email: str
) -> typing.Optional[str]:

    user = _lookup_slack_user_by_email(email=email)
    if user is not None:
        return user.id


def _lookup_slack_user_by_id(
        user_id: str
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:

    if _users_cache_by_id is None:
        _refresh_users_cache()

    result = _users_cache_by_id.get(user_id)

    return result


def _iterate_emails() -> typing.KeysView[str]:
    if _users_cache_by_email is None:
        _refresh_users_cache()

    return _users_cache_by_email.keys()


def _iterate_email_and_user() -> typing.ItemsView[str, slacktivate.slack.classes.SlackUser]:
    if _users_cache_by_email is None:
        _refresh_users_cache()

    return _users_cache_by_email.items()


def _iterate_user_id_and_user() -> typing.ItemsView[str, slacktivate.slack.classes.SlackUser]:
    if _users_cache_by_id is None:
        _refresh_users_cache()

    return _users_cache_by_id.items()


def users_deactivate(
        config: slacktivate.input.config.SlacktivateConfig,
        dry_run: bool = False,
) -> typing.Union[typing.List[slacktivate.slack.classes.SlackUser], typing.Tuple[int, int, int]]:

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
    for user_email, user in _iterate_email_and_user():

        # check for exceptions, and skip them
        if SLACK_BOTS_DOMAIN in user_email:
            continue

        # if in the configuration file, user should be there, so skip
        if user_email in config_user_emails:
            continue

        # at this point, a user should not be in the Slack, and should
        # be deactivated
        users_to_deactivate.append(user)

    # if dry-run, return list
    if dry_run:
        return users_to_deactivate

    # now deactivate all at once
    deactivated_count = 0

    for user in users_to_deactivate:
        if slacktivate.slack.methods.user_deactivate(user):
            deactivated_count += 1

    return (
        len(_iterate_email_and_user()),
        len(users_to_deactivate),
        deactivated_count,
    )


def users_ensure(
        config: slacktivate.input.config.SlacktivateConfig,
        dry_run: bool = False,
        iterator_wrapper: typing.Optional[typing.Callable[[typing.Iterator], typing.Iterator]] = None,
) -> typing.Union[typing.Dict[str, typing.Dict[str, typing.Any]], typing.Dict[str, slacktivate.slack.classes.SlackUser]]:

    # refresh the user cache
    _refresh_users_cache()

    # get emails of cached users
    # NOTE: if needed to deal with alternate emails, would be here
    active_user_emails = [
        user_email
        for user_email in _iterate_emails()
    ]

    users_to_create = {}

    # iterate over all users in config
    for user_email, user_attributes in config.users.items():

        # user already exists
        if user_email.lower() in active_user_emails:
            continue

        users_to_create[user_email] = user_attributes

    # if dry-run, return list
    if dry_run:
        return users_to_create

    # create the users
    users_created = {}

    # default iterator wrapper
    if iterator_wrapper is None:
        iterator_wrapper = (lambda x: x)

    for user_email, user_attributes in iterator_wrapper(users_to_create.items()):

        # include all attributes because user is freshly created,
        # no risk to overwrite user-modified attributes
        processed_attributes = slacktivate.slack.methods.make_user_dictionary(
            attributes=user_attributes,
            include_naming=True,
            include_image=True,
            include_fields=True,
        )

        new_user = slacktivate.slack.methods.user_create(
            attributes=processed_attributes,
        )

        users_created[user_email] = new_user

    return users_created


def users_update(
        config: slacktivate.input.config.SlacktivateConfig,
        overwrite_name: typing.Optional[bool] = None,
        overwrite_image: typing.Optional[bool] = None,
        dry_run: bool = False,
        iterator_wrapper: typing.Optional[typing.Callable[[typing.Iterator], typing.Iterator]] = None,
) -> typing.Dict[str, slacktivate.slack.classes.SlackUser]:

    # refresh the user cache
    _refresh_users_cache()

    users_provisioned = {}

    # default iterator wrapper
    if iterator_wrapper is None:
        iterator_wrapper = (lambda x: x)

    # NOTE: make the dry run return something
    if dry_run:
        return {}

    user_errors = {}

    # iterate over all users in config
    for user_email, user_attributes in iterator_wrapper(config.users.items()):

        # lookup user in cache that was just refreshed
        user = _lookup_slack_user_by_email(email=user_email)

        # only interested in users both in:
        #  1. the configuration file AND
        #  2. the Slack enrollment
        if user is None:
            continue
        user = typing.cast(slacktivate.slack.classes.SlackUser, user)

        # determine what are the overwriting rules

        keep_name = config.settings.get(
            slacktivate.input.config.SETTING_KEEP_CUSTOMIZED_NAME,
            True,
            )

        keep_photo = config.settings.get(
            slacktivate.input.config.SETTING_KEEP_CUSTOMIZED_PHOTOS,
            True,
        )

        if overwrite_name is not None:
            keep_name = not overwrite_name

        if overwrite_image is not None:
            keep_photo = not overwrite_image

        # change name if necessary

        if not keep_name:
            try:
                slacktivate.slack.methods.user_patch(
                    user=user,
                    changes=slacktivate.slack.methods.make_user_dictionary(
                        attributes=user_attributes,
                        include_naming=True,
                        include_image=False,
                        include_fields=False,
                    )
                )
            except Exception as exc:
                user_errors[user.email] = exc

        # change image if necessary

        user_image_type = slacktivate.helpers.photo.detect_profile_image_type(
            image_url=user.image_url,
            directory_img=user_attributes.get("image_url"),
        )

        if (
                # there is an available image for this user
                user_attributes.get("image_url") is not None and (

                    # either the image is None or Anonymous
                    (
                        user_image_type == slacktivate.helpers.photo.ProfileImageType.NONE or
                        user_image_type == slacktivate.helpers.photo.ProfileImageType.ANONYMOUS
                    )
                    or
                    # it is okay to replace it
                    not keep_photo
                )
        ):
            slacktivate.slack.methods.user_image_set(
                user=user,
                image_url=user_attributes.get("image_url"),
            )

        # change fields

        result = slacktivate.slack.methods.user_profile_set(
            user=user,
            extra_fields=slacktivate.slack.methods.make_user_extra_fields_dictionary(
                attributes=user_attributes,
            )
        )

        users_provisioned[user_email] = result
    print(user_errors)
    return users_provisioned


def groups_ensure(
        config: slacktivate.input.config.SlacktivateConfig,
        remove_unspecified_members: typing.Optional[bool] = None,
) -> typing.Dict[str, slacktivate.slack.classes.SlackGroup]:

    # refresh the user cache
    _refresh_users_cache()

    # lookup setting
    if remove_unspecified_members is None:
        remove_unspecified_members = not config.settings.get(
            slacktivate.input.config.SETTING_EXTEND_GROUP_MEMBERSHIPS,
            False
        )

    groups_created = dict()

    # iterate over all users in config
    for group_def in config.groups:

        group_display_name = group_def.get("name")
        if group_display_name is None or group_display_name == "":
            continue

        group_user_ids = list(map(
            lambda user: _lookup_slack_user_id_by_email(user["email"]),
            group_def["users"]
        ))

        group_obj = slacktivate.slack.methods.group_ensure(
            display_name=group_display_name,
            user_ids=group_user_ids,
            remove_unspecified_members=remove_unspecified_members,
        )

        if group_obj is not None:
            groups_created[group_display_name] = group_obj

    return groups_created


# noinspection PyBroadException
def channels_ensure(
        config: slacktivate.input.config.SlacktivateConfig,
        remove_unspecified_members: typing.Optional[bool] = None,
) -> typing.Optional[typing.Dict[str, str]]:

    # refresh the user cache
    _refresh_users_cache()

    # lookup setting
    if remove_unspecified_members is None:
        remove_unspecified_members = not config.settings.get(
            slacktivate.input.config.SETTING_EXTEND_CHANNEL_MEMBERSHIPS,
            False
        )

    # query channel data
    channels_by_name = slacktivate.slack.methods.channels_list()

    channels_created = dict()

    # iterate over all users in config
    for channel_def in config.channels:

        channel_name = channel_def.get("name")
        if channel_name is None or channel_name == "":
            continue

        channel_is_private = False if "private" not in channel_def else channel_def.get("private") == True

        existing_member_ids = set()

        if channel_name in channels_by_name:
            channel_id = channels_by_name.get(channel_name).get("id")

            # NOTE: shared used will be removed because won't be in
            # local user cache

            existing_members = list(filter(
                None.__ne__,
                map(_lookup_slack_user_by_id,
                    slacktivate.slack.methods.conversation_member_ids(
                        conversation_id=channel_id,
                    ))
            ))

            existing_member_ids = set(map(
                lambda member: member.id,
                existing_members
            ))

        else:
            # try to create the channel
            try:
                channel_id = slacktivate.slack.methods.channel_create(
                    name=channel_name,
                    is_private=channel_is_private,
                )
                channels_created[channel_name] = channel_id
            except:
                # probably already exists, but private or inaccessible to
                # user (NOTE: handle this better, maybe log?)
                continue

        if channel_id is None:
            continue

        # compute user IDs of provided members

        provided_member_ids = set(filter(
            None.__ne__,
            map(
                lambda user: _lookup_slack_user_id_by_email(user["email"]),
                channel_def["users"]
            )))

        # users to add, users to remove
        member_ids_to_invite = list(provided_member_ids.difference(existing_member_ids))
        member_ids_to_kick = list(existing_member_ids.difference(provided_member_ids))

        try:
            with slacktivate.slack.clients.managed_api() as client:
                client.conversations_invite(
                    channel=channel_id,
                    users=",".join(member_ids_to_invite),
                )
        except:
            pass

        if remove_unspecified_members:
            for member_id_to_kick in member_ids_to_kick:
                try:
                    with slacktivate.slack.clients.managed_api() as client:
                        client.conversations_kick(
                            channel=channel_id,
                            user=member_id_to_kick,
                        )
                except:
                    continue

    return channels_created

