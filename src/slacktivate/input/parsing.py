
import collections
import io
import json
import os
import typing

import yaml


def _flatten(
        lst: typing.Iterable,
        as_generator: bool = False
) -> typing.Union[typing.Generator, typing.List]:

    # from: https://stackoverflow.com/a/2158532/408734
    def _flatten_aux(lst: typing.Iterable):
        for x in lst:
            if (
                    isinstance(x, collections.abc.Iterable) and
                    not isinstance(x, (str, bytes))
            ):
                yield from _flatten_aux(x)
            else:
                yield x

    gen = _flatten_aux(lst=lst)

    if as_generator:
        return gen

    return list(gen)


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
    #     "substitutions": { "a": "A" },
    #     "fields": { "source": "file:student.json" },
    # }

    _required = ["type", ["file", "contents"]]
    _optional = ["substitutions", "fields"]

    def __init__(self, value):
        super().__init__(value)




class UserGroupConfig(SlacktivateConfigSection):
    # {
    #     "group_by": ["year"],
    #     "name": "phd-{year}",
    #     "filter": "$ where $.profile.degree == 'Ph.D.'",
    # }

    _required = ["name", "filter"]
    _optional = ["group_by"]

    pass


class ChannelConfig(SlacktivateConfigSection):
    # {
    #     "name": "phd-{year}",
    #     "groups": ["phd-*"],
    #     "private": true,
    # }

    _required = ["name"]
    _optional = ["groups", "private"]

    def __init__(self, value):
        super().__init__(value)



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

    d = yaml.load(io.StringIO(contents))

    return d
