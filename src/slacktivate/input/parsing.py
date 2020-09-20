
import collections
import copy
import fnmatch
import io
import itertools
import json
import os
import typing

import comma
import yaml

import slacktivate.input.helpers


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "SlacktivateJSONEncoder",
    "SlacktivateConfigError",
    "SlacktivateConfigSection",

    "UserSourceConfig",
    "UserGroupConfig",
    "ChannelConfig",

    "parse_specification",
]


class SlacktivateJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, SlacktivateConfigSection):
            try:
                result = super().default(
                    obj._repr_dict_()
                )
            except TypeError:
                pass

        try:
            result = super().default(obj)
            return result
        except TypeError:
            pass


class SlacktivateConfigError(ValueError):
    pass


class SlacktivateConfigSection(collections.UserDict):

    _required = []
    _optional = []
    _strict = True

    def __init__(self, value, **kwargs):
        super().__init__(value, **kwargs)
        self._validate_fields()

    def _validate_fields(self):

        # check required fields
        if self._required is not None:
            missing_required = []

            for field_or_fields in self._required:

                if type(field_or_fields) is str:
                    if field_or_fields not in self:
                        missing_required.append(field_or_fields)

                elif isinstance(field_or_fields, list):
                    missing = True
                    for field in field_or_fields:
                        if field in self:
                            missing = False
                    if missing:
                        missing_required.append(field_or_fields)

            if len(missing_required) > 0:
                raise SlacktivateConfigError(
                    "missing required fields: {}".format(missing_required)
                )

        # check there are no other fields if strict validation
        if self._strict:
            _possible_fields = slacktivate.input.helpers.flatten([self._required, self._optional])
            for key in self.keys():
                if key not in _possible_fields:
                    raise SlacktivateConfigError(
                        ("strict validation of configuration {cls}; "
                         "found field '{field}' not from: {expected}").format(
                            cls=self.__class__.__name__,
                            field=key,
                            expected=_possible_fields,
                        )
                    )

    def _repr_dict_(self) -> dict:
        return dict(self)


class UserSourceConfig(SlacktivateConfigSection):
    # {
    #     "file": "filename.json",
    #     "type": "json",
    #     "contents": "...",
    #     "key": "{{ email }}",
    #     "fields": { "source": "file:student.json" },
    # }

    _required = ["type", ["file", "contents"]]
    _optional = ["fields", "key", "filter"]

    def __init__(self, value):
        super().__init__(value)

        if "file" in self:
            assert os.path.exists(self.get("file")), "check user config exists"

        if "key" in self:
            assert slacktivate.input.helpers.parseable_jinja2(self.get("key")), "check 'key' field"

    def _load(self) -> list:

        raw_data = None

        # getting the data
        if "file" in self:
            raw_data = open(self.get("file")).read()

        elif "contents" in self:
            raw_data = self.get("contents")

        data = None

        # converting it in right format
        if self.get("type") == "json":
            data = json.loads(raw_data)

        elif self.get("type") == "yaml":
            data = yaml.load(raw_data)

        elif self.get("type") == "csv":
            data = comma.load(raw_data)

        return data

    def _post_process(self, value: typing.Union[list, dict]) -> list:

        # the 'key' field is to reindex the database
        if "key" in self and self.get("key") is not None:

            key_pattern = self.get("key")

            # reindex data
            value = slacktivate.input.helpers.reindex_user_data(
                user_data=value,
                key=key_pattern,
            )

            # store the key
            for record in value.values():
                record["key"] = key_pattern

        # create additional programmable fields
        if "fields" in self and self.get("fields") is not None:

            def __expand_record(record):
                new_fields = {
                    field_name: slacktivate.input.helpers.render_jinja2(
                        jinja2_pattern=field_pattern,
                        data=record,
                    )
                    for field_name, field_pattern in self.get("fields").items()
                }
                record.update(new_fields)
                return record

            if issubclass(type(value), list) or issubclass(type(value), collections.UserList):
                value = [
                    __expand_record(record)
                    for record in value
                ]

            if issubclass(type(value), dict) or issubclass(type(value), collections.UserDict):
                value = {
                    key: __expand_record(record)
                    for key, record in value.items()
                }

        # refilter data
        if "filter" in self and self.get("fields") is not None:
            value = slacktivate.input.helpers.refilter_user_data(
                user_data=value,
                filter_query=self.get("filter"),
                reindex=self.get("key") is not None,
            )

        return value

    def load(self) -> list:
        data = self._load()
        data = self._post_process(data)
        return data


class UserGroupConfig(SlacktivateConfigSection):
    # {
    #     "name": "phd-{{ year }}",
    #     "filter": "$ where $.profile.degree == 'Ph.D.'",
    # }

    _required = ["name"]
    _optional = ["filter"]

    def __init__(self, value):
        super().__init__(value)

        if "name" in self:
            assert slacktivate.input.helpers.parseable_jinja2(self.get("name")), "check 'name' field"

        if "filter" in self:
            assert slacktivate.input.helpers.parseable_yaql(self.get("filter", "")), "check filter is parseable"

    def compute(
            self,
            users: typing.Union[list, dict]
    ) -> typing.List["UserGroupConfig"]:

        target_users = users

        if self.get("filter") is not None:
            target_users = slacktivate.input.helpers.refilter_user_data(
                user_data=target_users,
                filter_query=self.get("filter"),
                reindex=False,
            )

        subgroup_users = {}

        for user in slacktivate.input.helpers.unindex_data(target_users):

            group_name = slacktivate.input.helpers.render_jinja2(
                jinja2_pattern=self.get("name"),
                data=user,
            )

            subgroup_users[group_name] = subgroup_users.get(group_name, list())
            subgroup_users[group_name].append(user)

        groups = []

        for subgroup_name, subgroup_membership in subgroup_users.items():

            group = copy.deepcopy(self)

            group.update({
                "name": subgroup_name,
                "users": subgroup_membership,
            })

            groups.append(group)

        return groups


class ChannelConfig(SlacktivateConfigSection):
    # {
    #     "name": "phd-{{ year }}",
    #     "groups": ["phd-*"],
    #     "filter": "$ where $.profile.degree == 'Ph.D.'",
    #     "private": true,
    #     "permissions": "user",
    # }

    _required = ["name"]
    _optional = ["groups", "private", "filter", "permissions"]

    def __init__(self, value):
        super().__init__(value)

        if "name" in self:
            assert slacktivate.input.helpers.parseable_jinja2(self.get("name")), "check 'name' field"

        if "filter" in self:
            assert slacktivate.input.helpers.parseable_yaql(self.get("filter", "")), "check filter is parseable"

    def compute(
            self,
            users: typing.Union[list, dict],
            groups: typing.List[UserGroupConfig],
    ) -> typing.List["ChannelConfig"]:

        target_users = users

        if self.get("groups") is not None:
            group_globs = self.get("groups")

            if type(group_globs) is str:
                group_globs = [group_globs]

            group_names = list(map(lambda grp: grp.get("name"), groups))
            globbed_names = list(set(itertools.chain(*[
                    fnmatch.filter(group_names, group_glob)
                    for group_glob in group_globs
                ])))

            target_users = list(itertools.chain(*[
                grp.get("users")
                for grp in groups
                if grp.get("name") in globbed_names
            ]))

            target_users = slacktivate.input.helpers.deduplicate_user_data(
                target_users
            )

        if self.get("filter") is not None:
            target_users = slacktivate.input.helpers.refilter_user_data(
                user_data=target_users,
                filter_query=self.get("filter"),
                reindex=False,
            )

        subchannel_users = {}

        for user in slacktivate.input.helpers.unindex_data(target_users):

            channel_name = slacktivate.input.helpers.render_jinja2(
                jinja2_pattern=self.get("name"),
                data=user,
            )

            subchannel_users[channel_name] = subchannel_users.get(channel_name, list())
            subchannel_users[channel_name].append(user)

        channels = []

        for subchannel_name, subchanne_membership in subchannel_users.items():

            channel = copy.deepcopy(self)

            channel.update({
                "name": subchannel_name,
                "users": subchanne_membership,
            })

            channels.append(channel)

        return channels


def _raw_parse_specification(
        stream: typing.Optional[io.TextIOBase] = None,
        filename: typing.Optional[str] = None,
        contents: typing.Optional[str] = None,
) -> typing.Optional[dict]:
    if stream is not None:
        try:
            stream.seek(0)
        except io.UnsupportedOperation:
            pass
        contents = stream.read(),

    elif filename is not None and os.path.exists(filename):
        with open(filename, mode="r") as f:
            contents = f.read()

    elif contents is not None:
        pass

    else:
        # nothing is set
        raise ValueError(
            "no valid input source provided: "
            "stream, filename, contents all `None`"
        )

    obj = yaml.load(io.StringIO(contents), Loader=yaml.BaseLoader)

    return obj


def parse_specification(
        stream: typing.Optional[io.TextIOBase] = None,
        filename: typing.Optional[str] = None,
        contents: typing.Optional[str] = None,
) -> typing.Optional[dict]:

    obj = _raw_parse_specification(
        stream=stream,
        filename=filename,
        contents=contents,
    )

    if "users" in obj:
        obj["users"] = list(map(UserSourceConfig, obj["users"]))

    if "groups" in obj:
        obj["groups"] = list(map(UserGroupConfig, obj["groups"]))

    if "channels" in obj:
        obj["channels"] = list(map(ChannelConfig, obj["channels"]))

    return obj
