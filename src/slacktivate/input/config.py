
import copy
import os
import io
import typing

import slacktivate.input.helpers
import slacktivate.input.parsing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [

    "SETTING_KEEP_CUSTOMIZED_PHOTOS",
    "SETTING_KEEP_CUSTOMIZED_NAME",
    "SETTING_EXTEND_GROUP_MEMBERSHIPS",
    "SETTING_EXTEND_CHANNEL_MEMBERSHIPS",
    "ALL_SETTINGS",
    
    "SlacktivateConfig",
]


SETTING_KEEP_CUSTOMIZED_PHOTOS = "keep_customized_photos"
SETTING_KEEP_CUSTOMIZED_NAME = "keep_customized_name"
SETTING_EXTEND_GROUP_MEMBERSHIPS = "extend_group_memberships"
SETTING_EXTEND_CHANNEL_MEMBERSHIPS = "extend_channel_memberships"

ALL_SETTINGS: typing.List[str] = [
    SETTING_KEEP_CUSTOMIZED_PHOTOS,
    SETTING_KEEP_CUSTOMIZED_NAME,
    SETTING_EXTEND_GROUP_MEMBERSHIPS,
    SETTING_EXTEND_CHANNEL_MEMBERSHIPS,
]


class SlacktivateConfig:

    _config: slacktivate.input.parsing.SlacktivateConfigSection = None
    _users: typing.Dict[str, typing.Dict] = None
    _groups: typing.List[slacktivate.input.parsing.UserGroupConfig] = None
    _channels: typing.List[slacktivate.input.parsing.ChannelConfig] = None

    def __init__(
            self,
            config_data: slacktivate.input.parsing.SlacktivateConfigSection,
    ):
        if config_data is None:
            raise ValueError("`config_data` not supposed to be None")

        self._config = config_data

        self._vars = self._config.get("vars", dict())

        self._users = {}

        self._alternate_emails = {}

        # Parsing booleans?
        for (key, value) in self._config.get("settings", dict()).items():
            if not type(value) is str:
                continue
            value = value.lower()
            if value == "true":
                self._config["settings"][key] = True
            if value == "false":
                self._config["settings"][key] = False

        if "alternate_emails" in self._config.get("settings", dict()):

            lines = None

            alternate_emails_src = self._config.get("settings").get("alternate_emails")
            if os.path.exists(alternate_emails_src):
                lines = open(alternate_emails_src).read().strip().splitlines(keepends=False)
            elif "\n" in alternate_emails_src:
                lines = alternate_emails_src.strip().splitlines()

            if lines is not None:
                lst_of_emails = list(map(lambda s: s.split(","), lines))
                dict_of_emails = {
                    email: email_row
                    for email_row in lst_of_emails
                    for email in email_row
                }
                self._alternate_emails = dict_of_emails

        for userconfig in self._config.get("users"):
            userconfig = typing.cast(slacktivate.input.parsing.UserSourceConfig, userconfig)
            users = userconfig.load(vars=self._vars, alternate_emails=self._alternate_emails)

            # merging with existing data

            old_users = self._users
            new_users = slacktivate.input.helpers.reindex_user_data(
                user_data=users,
            )

            for (key, user) in new_users.items():

                # new user, easy
                if key not in old_users:
                    old_users[key] = user
                    continue

                # existing user, need to merge carefully
                combined_user = slacktivate.input.helpers.merge_dict(
                    src=old_users[key],
                    dest=user,
                )
                old_users[key] = combined_user

            self._users = old_users

            # self._users.update(slacktivate.input.helpers.reindex_user_data(
            #     user_data=users,
            # ))

        self._groups = []

        for groupconfig in self._config.get("groups", list()):
            new_groups = groupconfig.compute(
                users=self._users,
                vars=self._vars,
            )
            self._groups += new_groups

        self._channels = []

        for channelconfig in self._config.get("channels", list()):
            new_channels = channelconfig.compute(
                users=self._users,
                groups=self._groups,
                vars=self._vars,
            )
            self._channels += new_channels

    @classmethod
    def from_specification(
            cls,
            stream: typing.Optional[io.TextIOBase] = None,
            filename: typing.Optional[str] = None,
            contents: typing.Optional[str] = None,
            config_data: typing.Optional[slacktivate.input.parsing.SlacktivateConfigSection] = None,
    ):
        if stream is not None or filename is not None or contents is not None:
            config_data = slacktivate.input.parsing.parse_specification(
                stream=stream,
                filename=filename,
                contents=contents,
            )

        if config_data is None:
            return

        return cls(config_data=config_data)

    @property
    def users(self) -> typing.Dict[str, typing.Dict]:
        return copy.deepcopy(self._users)

    @property
    def groups(self) -> typing.List[slacktivate.input.parsing.UserGroupConfig]:
        return copy.deepcopy(self._groups)

    @property
    def channels(self) -> typing.List[slacktivate.input.parsing.ChannelConfig]:
        return copy.deepcopy(self._channels)

    @property
    def settings(self) -> typing.Dict[str, typing.Any]:
        return copy.deepcopy(self._config.get("settings", dict()))
