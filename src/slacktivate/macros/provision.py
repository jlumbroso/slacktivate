
"""
This submodule contains a number of high-level macros that focus on
the provisioning/deprovisioning of Slack users, in particular using
the Slack SCIM API.
"""

import typing

import loguru

import slacktivate.helpers.photo
import slacktivate.input.config
import slacktivate.input.helpers
import slacktivate.input.parsing
import slacktivate.slack.classes
import slacktivate.slack.clients
import slacktivate.slack.methods


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "users_iterate",
    "users_list",

    "users_deactivate",
    "users_ensure",
    "users_update",

    "groups_ensure",

    "channels_ensure",
]


# Submodule constants

MAX_USER_LIMIT = 1000
"""
The Slack API and Slack SCIM API maximum limit when returning paginated
results (of users, channels, etc.).
"""

SLACK_BOTS_DOMAIN = "@slack-bots.com"
"""
Domain name of email addresses associated with Slack apps and bots. This
is useful to filter out these bots when listing users, for instance, with
:py:func:`users_list`.
"""

DRY_RUN_BY_DEFAULT = False
"""
Global flag to indicate whether operations in this module should be
dry-runs by default or not. If this flag is set to :py:data:`True`,
all operations will return changes that will be made but will not
actually carry them out unless the argument ``dry_run=True`` is
provided the methods in question.
"""


# Submodule global variables

_users_cache_by_email: typing.Optional[typing.Dict[str, slacktivate.slack.classes.SlackUser]] = None
"""Internal cache of the users, indexed by their *primary email*, in the
currently logged-in Slack workspace, to speed up queries."""

_users_cache_by_id: typing.Optional[typing.Dict[str, slacktivate.slack.classes.SlackUser]] = None
"""Internal cache of the users, indexed by their *Slack user ID*, in the
currently logged-in Slack workspace, to speed up queries."""


# Logger
logger = loguru.logger


def _refresh_users_cache(index_by_alternate_emails=False) -> typing.NoReturn:
    """
    Refreshes the two global internal caches of users (:py:attr:`_users_cache_by_email`
    and :py:attr:`_users_cache_by_id`) that this module uses to speed up queries
    over users and avoid hitting rate-limiting quotas too frequently.

    :param index_by_alternate_emails: Flag to indicate whether all the emails of
        the users (i.e., including the alternate ones) should be indexed in the cache,
        or only the primary email.
    :type index_by_alternate_emails: :py:class:`bool`
    """
    global _users_cache_by_email, _users_cache_by_id

    result = slacktivate.slack.clients.scim().search_users(count=MAX_USER_LIMIT)
    logger.debug("Retrieved {} users from Slack SCIM API.", len(result.resources))

    _users_cache_by_email = dict()
    _users_cache_by_id = dict()

    for resource in result.resources:

        # create wrapper around user
        user = slacktivate.slack.classes.SlackUser(resource=resource)
        if user is None or not user.exists:
            continue

        logger.debug("Caching user {} ({}) active: {}...", user.email, user.id, user.active)

        # index by primary email
        _users_cache_by_email[user.email] = user

        # index by secondary emails
        if index_by_alternate_emails:
            for email in user.emails:
                _users_cache_by_email[email] = user

        # index by id
        _users_cache_by_id[user.id] = user


def _lookup_slack_user_by_email(
        email: str,
        refresh: typing.Optional[bool] = None,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    """
    Returns a :py:class:`slacktivate.slack.classes.SlackUser` object
    representing the user associated with the provided :py:data:`email`
    in the currently logged-in Slack workspace, if such a user can be
    found.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param email: An email address to lookup
    :type email: :py:class:`str`

    :param refresh: Flag to indicate whether the cache should be refreshed
        before looking up the email address
    :type refresh: :py:class:`bool`

    :return: The user associated with the email, or :py:data:`None`
    :rtype: :py:class:`slacktivate.slack.classes.SlackUser` or :py:data:`None`
    """

    if _users_cache_by_email is None or (refresh is not None and refresh):
        _refresh_users_cache()

    email = email.lower()

    result = _users_cache_by_email.get(email)

    return result


def _lookup_slack_user_id_by_email(
        email: str,
        refresh: typing.Optional[bool] = None,
) -> typing.Optional[str]:
    """
    Returns a Slack user ID representing the user associated with the
    provided :py:data:`email` in the currently logged-in Slack workspace,
    if such a user can be found.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param email: An email address to lookup
    :type email: :py:class:`str`

    :param refresh: Flag to indicate whether the cache should be refreshed
        before looking up the email address
    :type refresh: :py:class:`bool`

    :return: The Slack user ID associated with the email, or :py:data:`None`
    :rtype: :py:class:`str` or :py:data:`None`
    """

    user = _lookup_slack_user_by_email(
        email=email,
        refresh=refresh,
    )
    if user is not None:
        return user.id


def _lookup_slack_user_by_id(
        user_id: str,
        refresh: typing.Optional[bool] = None,
) -> typing.Optional[slacktivate.slack.classes.SlackUser]:
    """
    Returns a :py:class:`slacktivate.slack.classes.SlackUser` object
    representing the user associated with the provided Slack user ID
    in the currently logged-in Slack workspace, if such a user can be
    found.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param user_id: A valid Slack user ID
    :type user_id: :py:class:`str`

    :param refresh: Flag to indicate whether the cache should be refreshed
        before looking up the Slack user ID
    :type refresh: :py:class:`bool`

    :return: The user associated with the Slack user ID, or :py:data:`None`
    :rtype: :py:class:`slacktivate.slack.classes.SlackUser` or :py:data:`None`
    """

    if _users_cache_by_id is None or (refresh is not None and refresh):
        _refresh_users_cache()

    result = _users_cache_by_id.get(user_id)

    return result


def _iterate_emails(
        refresh: typing.Optional[bool] = None
) -> typing.KeysView[str]:
    """
    Returns an iterator over all the (primary) emails of the existing users
    in the currently logged-in Slack workspace.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param refresh: Flag to indicate whether the cache should be refreshed
    :type refresh: :py:class:`bool`

    :return: An iterator over the primary email addresses
    """

    if _users_cache_by_email is None or (refresh is not None and refresh):
        _refresh_users_cache()

    return _users_cache_by_email.keys()


def _iterate_email_and_user(
        refresh: typing.Optional[bool] = None
) -> typing.ItemsView[str, slacktivate.slack.classes.SlackUser]:
    """
    Returns an iterator over all pairs of ``(primary email, user object)``
    of the existing users in the currently logged-in Slack workspace.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param refresh: Flag to indicate whether the cache should be refreshed
    :type refresh: :py:class:`bool`

    :return: An iterator over pairs of primary email address and user object
    """

    if _users_cache_by_email is None or (refresh is not None and refresh):
        _refresh_users_cache()

    return _users_cache_by_email.items()


def _iterate_user_id_and_user(
        refresh: typing.Optional[bool] = None
) -> typing.ItemsView[str, slacktivate.slack.classes.SlackUser]:
    """
    Returns an iterator over all pairs of ``(Slack user ID, user object)``
    of the existing users in the currently logged-in Slack workspace.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    :param refresh: Flag to indicate whether the cache should be refreshed
    :type refresh: :py:class:`bool`

    :return: An iterator over pairs of Slack user ID and user object
    """

    if _users_cache_by_id is None or (refresh is not None and refresh):
        _refresh_users_cache()

    return _users_cache_by_id.items()


def users_iterate(
        only_active: bool = True,
        only_email: bool = False,
        no_bots: bool = True,
        refresh: typing.Optional[bool] = None,
) -> typing.Union[
    typing.KeysView[str],
    typing.ItemsView[str, slacktivate.slack.classes.SlackUser]
]:
    """
    Returns an iterator over the existing users in the Slack workspace.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    This method is implemented using a collection of related internal
    methods, and should be the main mechanism by which to iterate over
    users.

    :param only_active: Flag to only return active users
    :param only_email: Flag to iterate over emails, not ``(email, user)`` pairs
    :param no_bots: Flag to filter out bot users
    :param refresh: Flag to force a refresh of the cache

    :return: An iterator over the existing users in the Slack workspace,
        either over a sequence of ``str`` representing emails (if ``only_email``
        is set to ``True``) or a pair of ``str`` and
        :py:class:`slacktivate.slack.classes.SlackUser` representing,
        respectively, the primary email and the user object.
    """

    iterator = _iterate_email_and_user(refresh=refresh)

    if no_bots:
        iterator = filter(
            lambda email_user_pair: SLACK_BOTS_DOMAIN not in email_user_pair[0],
            iterator,
        )

    if only_active:
        iterator = filter(
            lambda email_user_pair: email_user_pair[1].scim_obj.to_dict().get("active", False),
            iterator,
        )

    if only_email:
        iterator = map(
            lambda email_user_pair: email_user_pair[0],
            iterator,
        )

    return iterator


def users_list(
        only_active: typing.Optional[bool] = True,
        only_email: bool = False,
        no_bots: bool = True,
        as_dict: typing.Optional[bool] = None,
        refresh: typing.Optional[bool] = None,
) -> typing.Union[
    typing.List[str],
    typing.List[typing.Tuple[str, slacktivate.slack.classes.SlackUser]],
    typing.Dict[str, slacktivate.slack.classes.SlackUser],
]:
    """
    Returns a list (or dictionary) of the existing users in the Slack workspace.

    This method uses an internal caching mechanism that can be
    bypassed with the parameter :py:data:`refresh` or by calling the
    internal method :py:func:`_refresh_users_cache`.

    This method is implemented using a collection of related internal
    methods, and should be the main mechanism by which to iterate over
    users.

    :param only_active: Flag to only return active users
    :param only_email: Flag to iterate over emails, not ``(email, user)`` pairs
    :param no_bots: Flag to filter out bot users
    :param as_dict: Flag to determine whether to return a list or dictionary
    :type as_dict: bool
    :param refresh: Flag to force a refresh of the cache
    :type refresh: bool

    :return: A list of emails, or ``(email, user)`` pairs; or a dictionary mapping
        emails to users, of the existing users in the Slack workspace.
    """

    iterator = users_iterate(
        only_active=only_active,
        only_email=only_email,
        no_bots=no_bots,
        refresh=refresh,
    )

    ret = list(iterator)

    if as_dict is not None and as_dict and not only_email:
        ret = dict(ret)

    return ret


def users_deactivate(
        config: slacktivate.input.config.SlacktivateConfig,
        only_active: bool = False,
        dry_run: bool = False,
) -> typing.Tuple[typing.List[slacktivate.slack.classes.SlackUser], typing.Tuple[int, int, int]]:
    """
    Deactivates all users that are not described in the provided :py:data:`config`
    parameter of type :py:class:`SlacktivateConfig`.

    :param config: A :py:class:`SlacktivateConfig` object storing the compiled
        Slacktivate specification for this workspace
    :param only_active: Flag to only update users that are currently active
    :param dry_run: Flag to only return users to be deactivated, rather than
        taking the action of deactivating them

    :return: If :py:data:`dry_run` is set to :py:data:`True`, then the list of
        :py:class:`SlackUser` of the users to be deactivated; otherwise a tuple
        summarizing the number of users that were examined, that were to be
        deactivated, and that were successfully deactivated
    """

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

        # if only active users should be provided (the diff'), skip
        # if not active
        if only_active and not user.active:
            continue

        # at this point, a user should not be in the Slack, and should
        # be deactivated
        users_to_deactivate.append(user)

    # if dry-run, return list
    if dry_run:
        return (
            users_to_deactivate,
            (0, 0, 0)
        )

    # now deactivate all at once
    deactivated_count = 0

    users_deactivated = []
    for user in users_to_deactivate:
        if slacktivate.slack.methods.user_deactivate(user):
            users_deactivated.append(user)
            deactivated_count += 1

    return (
        users_deactivated,
        (
            len(_iterate_email_and_user()),
            len(users_to_deactivate),
            deactivated_count,
        )
    )


def users_ensure(
        config: slacktivate.input.config.SlacktivateConfig,
        dry_run: bool = False,
        iterator_wrapper: typing.Optional[typing.Callable[[typing.Iterator], typing.Iterator]] = None,
) -> typing.Union[
    typing.Dict[str, typing.Dict[str, typing.Any]],
    typing.Dict[str, slacktivate.slack.classes.SlackUser]
]:
    """
    Ensures that all users specified by the provided Slackativate configuration,
    :py:data:`config`, have been provisioned and are active in the Slack workspace.

    This method does nothing to deactivate users that are not specified in the
    configuration---this is handled by a separate method, :py:func:`users_deactivate`.

    :param config: A :py:class:`SlacktivateConfig` object storing the compiled
        Slacktivate specification for this workspace
    :param dry_run: Flag to only return users to be created, rather than taking
        the action of creating them
    :param iterator_wrapper: Optional iterator wrapper, to post-process the pairs
        of ``(email, user attributes)`` in some way before that information is
        used to create users

    :return: If :py:attr:`dry_run` is set to :py:data:`True`, returns a dictionary
        mapping primary emails to the Slack payload that will be used to create
        the user; otherwise, returns a dictionary mapping emails to the created
        user objects
    """

    # refresh the user cache
    _refresh_users_cache()

    # get emails of cached users
    # NOTE: if needed to deal with alternate emails, would be here
    active_user_emails = [
        user_email.lower()
        for user_email, user in _iterate_email_and_user()
        if user.active
    ]
    existing_user_emails = [
        user_email.lower()
        for user_email, user in _iterate_email_and_user()
    ]
    logger.debug("Active user emails (count: {}): {}", len(active_user_emails), active_user_emails)
    logger.debug("Existing user emails (count: {}): {}", len(existing_user_emails), existing_user_emails)

    users_to_create = {}

    # iterate over all users in config
    for user_email, user_attributes in config.users.items():

        logger.info("Considering {} with {}", user_email, user_attributes)

        # user already exists
        if user_email.lower() in existing_user_emails:
            logger.info("=> {} in EXISTING users", user_email)

            # if user is not active, warn
            if user_email.lower() not in active_user_emails:
                logger.info("=> {} in ACTIVE users", user_email)
                logger.warning("User {} is not active, but exists: Need to use `synchronize` to reactivate", user_email)

            continue
        
        # user does not exist, so create
        logger.info("=> {} does not exist and will be created", user_email)

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

        try:
            new_user = slacktivate.slack.methods.user_create(
                attributes=processed_attributes,
            )
        except slacktivate.slack.clients.SCIMApiError as exc:
            logger.error(
                "Failed to create user {email} [{exists}] with attributes {attributes}: {exc}",
                email=user_email,
                exists=user_email.lower() in existing_user_emails,
                attributes=user_attributes,
                exc=exc,
            )
            continue

        users_created[user_email] = new_user

    return users_created


def users_update(
        config: slacktivate.input.config.SlacktivateConfig,
        overwrite_name: typing.Optional[bool] = None,
        overwrite_image: typing.Optional[bool] = None,
        dry_run: bool = False,
        iterator_wrapper: typing.Optional[typing.Callable[[typing.Iterator], typing.Iterator]] = None,
) -> typing.Dict[str, slacktivate.slack.classes.SlackUser]:
    """
    Updates the profile information of users specified by the provided
    Slackativate configuration, :py:data:`config`, of which the accounts have
    already been created.

    This method does not create new users (which can be done with
    :py:func:`users_ensure`) or deactivate existing users (which can be done
    with :py:func:`users_deactivate`), it only modifies profile attributes.

    :param config: A :py:class:`SlacktivateConfig` object storing the compiled
        Slacktivate specification for this workspace
    :param overwrite_name: Flag to determine whether to allow this method to
        overwrite customized names set by the user
    :param overwrite_image: Flag to determine whether to allow this method to
        overwrite customized profile images set by users
    :param dry_run: Flag to only return users whose profile will be modified,
        rather than taking the action of modifying them
    :param iterator_wrapper: Optional iterator wrapper, to post-process the pairs
        of ``(email, user attributes)`` in some way before that information is
        used to update user profiles

    :return: A dictionary of mapping primary emails to the user objects for
        the modified users
    """

    # refresh the user cache
    _refresh_users_cache()

    users_provisioned = {}

    # default iterator wrapper
    if iterator_wrapper is None:
        iterator_wrapper = (lambda x: x)

    # FIXME: improve dry-run
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

    return users_provisioned


def groups_ensure(
        config: slacktivate.input.config.SlacktivateConfig,
        remove_unspecified_members: typing.Optional[bool] = None,
        dry_run: bool = False,
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

    # FIXME: improve dry-run
    if dry_run:
        return dict()

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
        dry_run: bool = False,
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
    channels_modifications = dict()

    # iterate over all users in config
    for channel_def in config.channels:

        channel_name = channel_def.get("name")
        if channel_name is None or channel_name == "":
            continue

        channel_id = None

        # compute whether channel is private
        channel_is_private = False if "private" not in channel_def else channel_def.get("private") == True

        # initialize the modifications' entry for dry_run
        channels_modifications[channel_name] = channels_modifications.get(channel_name, dict())

        # loop

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

            # store information
            channels_modifications[channel_name]["id"] = channel_id
            channels_modifications[channel_name]["exists"] = True
            channels_modifications[channel_name]["created"] = False
            channels_modifications[channel_name]["members_ids_existing"] = list(existing_member_ids)

        else:
            # store information
            channels_modifications[channel_name]["exists"] = False
            channels_modifications[channel_name]["created"] = False
            channels_modifications[channel_name]["members_ids_existing"] = list()

            if dry_run:
                # to indicate in output why action was not executed
                channels_modifications[channel_name]["dry_run"] = True

            else:
                # try to create the channel
                try:
                    channel_id = slacktivate.slack.methods.channel_create(
                        name=channel_name,
                        is_private=channel_is_private,
                    )
                    channels_created[channel_name] = channel_id

                    # store information
                    channels_modifications[channel_name]["id"] = channel_id
                    channels_modifications[channel_name]["exists"] = True
                    channels_modifications[channel_name]["created"] = True
                except:
                    # probably already exists, but private or inaccessible to
                    # user (NOTE: handle this better, maybe log?)
                    continue

        # compute user IDs of provided members

        provided_member_ids = set(filter(
            None.__ne__,
            map(
                lambda user: _lookup_slack_user_id_by_email(user["email"]),
                channel_def.get("users", list())
            )))

        # users to add, users to remove
        member_ids_to_invite = list(provided_member_ids.difference(existing_member_ids))
        member_ids_to_kick = list(existing_member_ids.difference(provided_member_ids))

        if not remove_unspecified_members:
            member_ids_to_kick = []

        # store that information
        channels_modifications[channel_name]["members_ids_to_invite"] = member_ids_to_invite
        channels_modifications[channel_name]["member_ids_to_kick"] = member_ids_to_kick

        # we computed the IDs to report the information back, but if `channel_id`
        # is non-existent, means we did not successfully create the channel
        if channel_id is None:
            continue

        # dry-run, we just record modifications not do them
        if dry_run is not None and dry_run:
            continue

        try:
            with slacktivate.slack.clients.managed_api(patch_reply_exception=True) as client:
                client.conversations_invite(
                    channel=channel_id,
                    users=",".join(member_ids_to_invite),
                )
            channels_modifications[channel_name]["members_ids_added"] = member_ids_to_invite[:]
        except:
            pass

        if dry_run is None or not dry_run:
            member_ids_removed = []

            for member_id_to_kick in member_ids_to_kick:
                try:
                    with slacktivate.slack.clients.managed_api(patch_reply_exception=True) as client:
                        client.conversations_kick(
                            channel=channel_id,
                            user=member_id_to_kick,
                        )
                        member_ids_removed.append(member_id_to_kick)
                except:
                    continue

            channels_modifications[channel_name]["members_ids_removed"] = member_ids_removed

    return channels_modifications

