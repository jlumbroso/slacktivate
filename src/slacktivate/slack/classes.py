
"""
This submodule provides a commong abstraction layer over the heterogeneous
object types provided by the Slack API client and the Slack SCIM client
modules.
"""

import datetime
import typing

import slack_scim
import slack_scim.v1.user
import slack_scim.v1.users

import slacktivate.helpers.collections
import slacktivate.slack.clients
import slacktivate.slack.retry


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "lookup_user_by_id",
    "lookup_user_by_username",
    "lookup_user_by_email",

    "lookup_group_by_id",
    "lookup_group_by_display_name",

    "SlackUser",
    "SlackUserTypes",
    "to_slack_user",

    "SlackGroup",
    "SlackGroupTypes",
    "SlackGroupMember",
    "to_slack_group",
]


_SLACK_PHOTOS_FIELD = "photos"
_SLACK_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_SLACK_FULLNAME_PATTERN = "{givenName} {familyName}"  # Western bias, sorry -_-


def _escape_filter_param(s: str) -> str:
    """
    Ensures there are no single quotes in the filter string, to be used internally
    when doing a SCIM query with user-provided parameters (to avoid injection).

    :param s: A string from which to remove single-quote characters

    :return: The string :py:data:`s` without single-quote characters
    """
    if s is None:
        return ""
    return s.replace("'", "")


def _scim_resource_to_scim_user(
        resource: slack_scim.v1.users.Resource
) -> slack_scim.v1.user.User:
    """
    Returns a ```User`` object from a ``Resource`` object (that is known
    to be correspond to a user), both from the :py:mod:`slack_scim` package,
    using those objects' own internal methods

    :param resource: The :py:class:`slack_scim.v1.users.Resource` object known to be a user
    :return: A :py:class:`slack_scim.v1.user.User` object
    """

    if resource is not None:
        return slack_scim.v1.user.User.from_dict(
            resource.to_dict()
        )


def _scim_resource_to_scim_group(
        resource: slack_scim.v1.users.Resource
) -> slack_scim.v1.users.Group:
    """
    Returns a ```Group`` object from a ``Resource`` object (that is known
    to be correspond to a group), both from the :py:mod:`slack_scim` package,
    using those objects' own internal methods

    :param resource: The :py:class:`slack_scim.v1.users.Resource` object known to be a group
    :return: A :py:class:`slack_scim.v1.user.Group` object
    """

    if resource is not None:
        return slack_scim.v1.users.Group.from_dict(
            resource.to_dict()
        )


# =============================================================================


@slacktivate.slack.retry.slack_retry
def lookup_user_by_id(user_id: str) -> typing.Optional[slack_scim.User]:
    """
    Returns the internal :py:class:`slack_scim.User` object for a Slack user
    in the currently logged-in workspace, given that user's Slack ID; if the
    Slack user ID does not correspond to an existing user, returns :py:data:`None`.
    This query is live.

    :param user_id: A Slack user ID
    :return: A :py:class:`slack_scim.User` object or :py:data:`None`
    """

    try:
        result = slacktivate.slack.clients.scim().read_user(user_id)
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return result


@slacktivate.slack.retry.slack_retry
def lookup_user_by_username(username: str) -> typing.Optional[slack_scim.User]:
    """
    Returns the internal :py:class:`slack_scim.User` object for a Slack user
    in the currently logged-in workspace, given that user's `username`; if the
    username does not correspond to an existing user, returns :py:data:`None`.
    This query is live.

    :param username: A Slack username
    :return: A :py:class:`slack_scim.User` object or :py:data:`None`
    """

    username = _escape_filter_param(username)

    # https://api.slack.com/scim#filter
    try:
        results = slacktivate.slack.clients.scim().search_users(
            filter="username eq '{}'".format(username),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    # because of the `eq` there shouldn't be more than one result
    return slacktivate.helpers.collections.first_or_none(results)


@slacktivate.slack.retry.slack_retry
def lookup_user_by_email(email: str) -> typing.Optional[slack_scim.User]:
    """
    Returns the internal :py:class:`slack_scim.User` object for a Slack user
    in the currently logged-in workspace, given **one** of that user's emails;
    if the email does not correspond to an existing user, returns :py:data:`None`.
    This query is live.

    :param email: An email address
    :return: A :py:class:`slack_scim.User` object or :py:data:`None`
    """

    email = _escape_filter_param(email)

    # https://api.slack.com/scim#filter
    try:
        results = slacktivate.slack.clients.scim().search_users(
            filter="email eq '{}'".format(email),
            count=1
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    # because of the `eq` there shouldn't be more than one result
    return slacktivate.helpers.collections.first_or_none(results)


class SlackUser:
    """
    This is a wrapper class to abstract the concept of Slack user across
    the various vendor-provided packages

    """

    _user: typing.Optional[slack_scim.User] = None

    _provided_email: typing.Optional[str] = None
    _provided_username: typing.Optional[str] = None

    # *************************************

    def __init__(
            self,
            user_id: typing.Optional[str] = None,
            username: typing.Optional[str] = None,
            email: typing.Optional[str] = None,
            user: typing.Optional[slack_scim.User] = None,
            resource: typing.Optional[slack_scim.v1.users.Resource] = None,
    ):
        """
        Instantiates

        :param user_id:
        :param username:
        :param email:
        :param user:
        :param resource:
        """
        self._provided_username = username
        self._provided_email = email

        if user_id is not None:
            self._user = lookup_user_by_id(user_id=user_id)
        if username is not None:
            self._user = lookup_user_by_username(username=username)
        if email is not None:
            self._user = lookup_user_by_email(email=email)
        if user is not None and isinstance(user, slack_scim.User):
            self._user = user
        if resource is not None and isinstance(resource, slack_scim.v1.users.Resource):
            user = _scim_resource_to_scim_user(resource=resource)
            self._user = user

    def refresh(self) -> bool:
        if self._user is not None:
            self._user = lookup_user_by_id(user_id=self._user.id)
            return True
        return False

    def __repr__(self) -> str:
        if self._user is not None:
            return "SlackUser[{id}, {userName}, {email}]".format(
                email=self._user.emails[0].value,
                **self._user.to_dict(),
            )
        return "SlackUser[undefined, {}, {}]".format(
            self._provided_username,
            self._provided_email,
        )

    # *************************************

    @classmethod
    def from_id(cls, user_id: str) -> "SlackUser":
        """
        Creates a :py:class:`SlackUser` wrapper object, given a **Slack user ID**.

        .. note::
            This is an internal package method that does not do any validation,
            and can result in :py:class:`SlackUser` representing non-existent
            users. Use the higher-level :py:func:`to_slack_user` method to do
            user validation.

        :param user_id: A Slack user ID
        :return: A :py:class:`SlackUser` object
        """

        return cls(user_id=user_id)

    @classmethod
    def from_username(cls, username: str) -> "SlackUser":
        """
        Creates a :py:class:`SlackUser` wrapper object, given a **Slack username**.

        .. note::
            This is an internal package method that does not do any validation,
            and can result in :py:class:`SlackUser` representing non-existent
            users. Use the higher-level :py:func:`to_slack_user` method to do
            user validation.

        :param username: A Slack user ID
        :return: A :py:class:`SlackUser` object
        """

        return cls(username=username)

    @classmethod
    def from_email(cls, email: str) -> "SlackUser":
        """
        Creates a :py:class:`SlackUser` wrapper object, given an **email address**.

        .. note::
            This is an internal package method that does not do any validation,
            and can result in :py:class:`SlackUser` representing non-existent
            users. Use the higher-level :py:func:`to_slack_user` method to do
            user validation.

        :param email: A Slack user ID
        :return: A :py:class:`SlackUser` object
        """

        return cls(email=email)

    @classmethod
    def from_user(cls, user: slack_scim.User) -> "SlackUser":
        """
        Creates a :py:class:`SlackUser` wrapper object, given a non-null
        :py:class:`slack_scim.User` object.

        :param user: A :py:class:`slack_scim.User` object
        :return: A :py:class:`SlackUser` object
        """
        return cls(user=user)

    @classmethod
    def from_string(cls, string: str) -> "SlackUser":
        """
        Creates a :py:class:`SlackUser` wrapper object, given a string that may
        represent either:

        1. a Slack user ID (alphanumeric string beginning by ``W`` or ``U`` as
           `described in the Slack API documentation
           <https://api.slack.com/changelog/2016-08-11-user-id-format-changes>`_),
        2. an email (string with no spaces containing an ``@``),
        3. or a Slack username.

        .. note::
            This is an internal package method that does not do any validation,
            and can result in :py:class:`SlackUser` representing non-existent
            users. Use the higher-level :py:func:`to_slack_user` method to do
            user validation.

        :param string: A string
        :return: A :py:class:`SlackUser` object
        """

        # https://api.slack.com/changelog/2016-08-11-user-id-format-changes
        if string.isalnum() and string[:1].upper() in ["W", "U"]:
            return cls.from_id(user_id=string)

        if "@" in string and " " not in string:
            return cls.from_email(email=string)

        return cls.from_username(username=string)

    @classmethod
    def from_any(
            cls,
            value: typing.Union[str, slack_scim.User, None]
    ) -> typing.Optional["SlackUser"]:
        """

        :param value:
        :return:
        """

        if value is None:
            return

        if isinstance(value, str):
            return cls.from_string(string=value)

        if isinstance(value, slack_scim.User):
            return cls.from_user(value)

    # *************************************

    @property
    def id(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.id

    @property
    def username(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.user_name

    @property
    def email(self) -> typing.Optional[str]:
        if self._user is not None:
            return self._user.emails[0].value
    
    @property
    def emails(self) -> typing.List[str]:
        if self._user is not None:
            return list(map(lambda x: x.value, self._user.emails or []))
        return []

    @property
    def fullname(self) -> typing.Optional[str]:
        if self._user is not None:
            return _SLACK_FULLNAME_PATTERN.format(**self._user.name.to_dict())

    # *************************************

    @property
    def scim_obj(self) -> slack_scim.User:
        return self._user

    @property
    def exists(self) -> bool:
        return self._user is not None

    @property
    def active(self) -> bool:
        if not self.exists:
            return False

        return self._user.active

    @property
    def image_url(self) -> typing.Optional[str]:
        if not self.exists:
            return

        if _SLACK_PHOTOS_FIELD not in self._user.__dict__:
            return

        photos = self._user.__dict__[_SLACK_PHOTOS_FIELD]

        if len(photos) < 1:
            return

        # NOTE: maybe look for the primary one instead of the first one
        return photos[0].value


SlackUserTypes = typing.Union[str, slack_scim.User, SlackUser]
"""
This is a type annotation to describe all the data types supported
by the :py:func:`to_slack_user` method:

1. a string (an email, or a Slack user ID or username as described
   in more detail in the documentation for :py:func:`SlackUser.from_string`),
2. a :py:class:`slack_scim.User` object, from the Slack API package,
3. an existing :py:class:`SlackUser` object.
"""


def to_slack_user(
        value: typing.Optional[SlackUserTypes],
        only_existing: bool = True,
) -> typing.Optional[SlackUser]:
    """

    :param value:
    :param only_existing:
    :return:
    """

    # if input value is already a SlackUser class, no need to create
    # a new one?
    if isinstance(value, SlackUser):
        user = value

    else:
        user = SlackUser.from_any(value=value)

    if not only_existing or user.exists:
        return user

    return


# =============================================================================


SlackGroupMember = typing.TypedDict(
    "SlackGroupMember",
    {
        "display": str,
        "value": str,
    },
    total=True,
)
"""
"""


@slacktivate.slack.retry.slack_retry
def lookup_group_by_id(group_id: str) -> typing.Optional[slack_scim.Group]:
    try:
        result = slacktivate.slack.clients.scim().read_group(group_id)
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return result


@slacktivate.slack.retry.slack_retry
def lookup_group_by_display_name(display_name: str) -> typing.Optional[slack_scim.Group]:
    display_name = _escape_filter_param(display_name)

    # https://api.slack.com/scim#filter
    try:
        result = slacktivate.slack.clients.scim().search_groups(
            filter="displayName eq '{}'".format(display_name),
            count=1,
        ).resources
    except slack_scim.SCIMApiError as err:
        # handle non-existing user error
        if err.status == 404:
            return
        # propagate error (if rate limiting, will be caught by decorator)
        raise

    return slacktivate.helpers.collections.first_or_none(result)


class SlackGroup:

    _group: typing.Optional[slack_scim.Group] = None

    _provided_display_name: typing.Optional[str] = None

    # *************************************

    def __init__(
            self,
            group_id: typing.Optional[str] = None,
            display_name: typing.Optional[str] = None,
            group: typing.Optional[slack_scim.Group] = None,
            resource: typing.Optional[slack_scim.v1.users.Resource] = None,
    ):
        self._provided_display_name = display_name

        if group_id is not None:
            self._group = lookup_group_by_id(group_id=group_id)
        if display_name is not None:
            self._group = lookup_group_by_display_name(display_name=display_name)
        if group is not None and isinstance(group, slack_scim.Group):
            self._group = group
        if resource is not None and isinstance(resource, slack_scim.v1.users.Resource):
            group = _scim_resource_to_scim_group(resource=resource)
            self._group = group

    def refresh(self) -> bool:
        if self._group is not None:
            self._group = lookup_group_by_id(group_id=self._group.id)
            return True
        return False

    def __repr__(self) -> str:
        if self._group is not None:
            return "SlackGroup[{id}, {displayName}]".format(
                **self._group.to_dict(),
            )
        return "SlackGroup[undefined, {}]".format(
            self._provided_display_name
        )

    # *************************************

    @classmethod
    def from_id(cls, group_id: str) -> "SlackGroup":
        return cls(group_id=group_id)

    @classmethod
    def from_display_name(cls, display_name: str) -> "SlackGroup":
        return cls(display_name=display_name)

    @classmethod
    def from_group(
            cls,
            group: typing.Union[slack_scim.Group, slack_scim.v1.users.Group]
    ) -> "SlackGroup":
        if isinstance(group, slack_scim.v1.users.Group):
            return cls(group_id=group.value)

        return cls(group=group)

    @classmethod
    def from_string(cls, string: str) -> "SlackGroup":

        # https://api.slack.com/types/usergroup
        if string.isalnum() and string[:1].upper() in ["S"]:
            try:
                group = lookup_group_by_id(group_id=string)
                if group is not None:
                    return cls.from_group(group=group)
            except slack_scim.SCIMApiError:
                pass

        return cls.from_display_name(display_name=string)

    @classmethod
    def from_any(
            cls,
            value: typing.Union[str, slack_scim.Group, slack_scim.v1.users.Group, None]
    ) -> typing.Optional["SlackGroup"]:
        if value is None:
            return

        if isinstance(value, str):
            return cls.from_string(string=value)

        if isinstance(value, slack_scim.Group):
            return cls.from_group(group=value)

        if isinstance(value, slack_scim.v1.users.Group):
            return cls.from_group(group=value)

    # *************************************

    @property
    def id(self) -> typing.Optional[str]:
        if self._group is not None:
            return self._group.id

    @property
    def display_name(self) -> typing.Optional[str]:
        if self._group is not None:
            return self._group.display_name

    @property
    def created(self) -> typing.Optional[datetime.datetime]:
        if self._group is not None:
            try:
                created_string = self._group.meta.created
                created_datetime = datetime.datetime.strptime(
                    created_string,
                    _SLACK_DATETIME_FORMAT)
                return created_datetime
            except AttributeError:
                return

    @property
    def members(self) -> typing.Optional[typing.List[SlackGroupMember]]:
        if self._group is not None:
            member_list = self._group.to_dict().get("members", list())
            return member_list

    @property
    def member_ids(self) -> typing.Optional[typing.List[str]]:
        member_list = self.members
        if member_list is not None:
            member_ids = [
                member["value"]
                for member in member_list
            ]
            return member_ids

    def get_members_as_users(self) -> typing.Optional[typing.List[SlackUser]]:
        member_ids = self.member_ids
        if member_ids is not None:
            return list(map(SlackUser.from_id, member_ids))

    # *************************************

    @property
    def exists(self) -> bool:
        return self._group is not None


SlackGroupTypes = typing.Union[str, slack_scim.Group, slack_scim.v1.users.Group, SlackGroup]
"""
This is a type annotation to describe all the data types supported
by the :py:func:`to_slack_group` method:

1. a string (a Slack group ID or group display name as described
   in more detail in the documentation for :py:func:`SlackGroup.from_string`),
2. a :py:class:`slack_scim.Group` object, from the Slack API package,
3. an existing :py:class:`SlackGroup` object.
"""


def to_slack_group(
        value: typing.Optional[SlackGroupTypes],
        only_existing: bool = True,
) -> typing.Optional[SlackGroup]:
    # if input value is already a SlackGroup class, no need to create
    # a new one?
    if isinstance(value, SlackGroup):
        group = value

    else:
        group = SlackGroup.from_any(value=value)

    if not only_existing or group.exists:
        return group

    return
