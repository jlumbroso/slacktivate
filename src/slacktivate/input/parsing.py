
import collections
import io
import json
import os
import typing

import yaml

import slacktivate.input.helpers


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
            _possible_fields = _flatten([self._required, self._optional])
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
    _optional = ["fields", "key"]

    def __init__(self, value):
        super().__init__(value)

        if "file" in self:
            assert os.path.exists(self.get("file")), "check user config exists"

        if "key" in self:
            assert slacktivate.input.helpers.parseable_jinja2(self.get("key")), "check 'key' field"



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


def _raw_load_specification(
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


def _load_specifications(
        stream: typing.Optional[io.TextIOBase] = None,
        filename: typing.Optional[str] = None,
        contents: typing.Optional[str] = None,
) -> typing.Optional[dict]:

    obj = _raw_load_specification(
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
