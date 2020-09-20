
import copy
import io
import typing

import slacktivate.input.helpers
import slacktivate.input.parsing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [

    "SETTING_KEEP_CUSTOMIZED_PHOTOS",
    "SETTING_KEEP_CUSTOMIZED_NAME",
    "SETTING_EXTEND_GROUP_MEMBERSHIPS",
    "ALL_SETTINGS",
    
    "SlacktivateConfig",
]


SETTING_KEEP_CUSTOMIZED_PHOTOS = "keep_customized_photos"
SETTING_KEEP_CUSTOMIZED_NAME = "keep_customized_name"
SETTING_EXTEND_GROUP_MEMBERSHIPS = "extend_group_memberships"

ALL_SETTINGS: typing.List[str] = [
    SETTING_KEEP_CUSTOMIZED_PHOTOS,
    SETTING_KEEP_CUSTOMIZED_NAME,
    SETTING_EXTEND_GROUP_MEMBERSHIPS
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

        self._users = {}

        for userconfig in self._config.get("users"):
            users = userconfig.load()
            self._users.update(slacktivate.input.helpers.reindex_user_data(
                user_data=users,
            ))

        self._groups = []

        for groupconfig in self._config.get("groups", list()):
            new_groups = groupconfig.compute(users=self._users)
            self._groups += new_groups

        self._channels = []

        for channelconfig in self._config.get("channels", list()):
            new_channels = channelconfig.compute(
                users=self._users,
                groups=self._groups,
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
