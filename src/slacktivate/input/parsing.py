
import collections
import copy
import glob
import fnmatch
import io
import itertools
import jinja2
import json
import os
import textwrap
import typing

import comma
import yaml
import yaml.parser

import slacktivate.helpers.dict_serializer
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


SLACKTIVATE_SORT_NEWEST = "newest"

SLACKTIVATE_SORT_OLDEST = "oldest"

SLACKTIVATE_DEFAULT_SORT = SLACKTIVATE_SORT_NEWEST

DEFAULT_EMAIL_INDEX = 0

EMAIL_FIELD_NAME = "email"  # used only for alternate_emails feature
ALTERNATE_EMAIL_FIELD_NAME = "alternate_emails"


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
        self._validate_fields(**kwargs)

    def _validate_fields(self, **kwargs):

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


class UserSourceException(ValueError):
    def __init__(self, message="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message = message

    def __str__(self):
        return self.message

    @property
    def message(self):
        return self._message if self._message is not None else ""


class UserSourceConfig(SlacktivateConfigSection):
    # {
    #     "file": "filename.json",
    #     "type": "json",
    #     "contents": "...",
    #     "key": "{{ email }}",
    #     "fields": { "source": "file:student.json" },
    # }

    _required = ["type", ["file", "contents"]]
    _optional = ["fields", "key", "filter", "sort"]
    _source_name = None

    def __init__(self, value):
        super().__init__(value)
        self._validate_fields(vars=None)

    def _validate_fields(
            self,
            vars: typing.Optional[typing.Dict[str, str]] = None,
            **kwargs,
    ) -> typing.NoReturn:

        # first validate parent logic
        super()._validate_fields(vars=vars, **kwargs)

        if "file" in self:

            # first determine if we need the 'vars', and only continue if we don't need
            # it or we need it and it is provided to this function --- yes the condition in
            # the if is redundant, but intentionally so)

            file_str = self.get("file")
            file_str_fields = slacktivate.input.helpers.find_jinja2_template_fields(file_str)

            if "vars" not in file_str_fields or ("vars" in file_str_fields and vars is not None):

                if len(file_str_fields) > 0:
                    file_str = slacktivate.input.helpers.render_jinja2(
                        jinja2_pattern=file_str,
                        data=None,
                        vars=vars,
                    )

                # next "file" could be either a path, or a glob expression;
                # we raise an exception if the path does not exist and the
                # expression does not glob

                if not os.path.exists(file_str) and len(glob.glob(file_str)) == 0:
                    # looks like debug code right??
                    # print("<<<{}>>>".format(file_str))
                    # print("<<<{}>>>".format(glob.glob(file_str)))
                    # print("<<<{}>>>".format(len(glob.glob(file_str))))
                    # print("configuration file problem: user source '{}' cannot be found\n(pwd: '{}')".format(
                    #     self.get("file"),
                    #     os.getcwd()))
                    raise UserSourceException(
                        "configuration file problem: user source '{}' cannot be found\n(pwd: '{}')".format(
                            self.get("file"),
                            os.getcwd()),
                    )

        if "key" in self:
            if not slacktivate.input.helpers.parseable_jinja2(self.get("key")):
                raise UserSourceException(
                    "configuration file problem: no 'key' field to process '{}'".format(
                        self.get("file")),
                )

    def _load(
            self,
            vars: typing.Optional[typing.Dict[str, str]],
    ) -> list:

        # revalidate fields with 'vars' in case the validation of filename was skipped
        self._validate_fields(vars=vars)

        raw_data = None

        # getting the data
        if "file" in self:
            file_str = slacktivate.input.helpers.render_jinja2(
                jinja2_pattern=self.get("file"),
                data=None,
                vars=vars,
            )

            files = glob.glob(file_str)

            # by default, sort is in increasing order of mtime
            # but if we want newest, we want the largest mtime first,
            # so that is reverse
            reverse_sort = (
                self.get("sort", SLACKTIVATE_DEFAULT_SORT) == SLACKTIVATE_SORT_NEWEST
            )

            files.sort(
                key=os.path.getmtime,
                reverse=reverse_sort,
            )

            # guaranteed to exist otherwise we would have raised an exception
            # above when validating parameters
            file = files[0]
            self._source_name = file

            raw_data = open(file).read()

        elif "contents" in self:
            raw_data = self.get("contents")

        data = None

        # converting it in right format
        if self.get("type") == "json":
            data = json.loads(raw_data)

        elif self.get("type") == "yaml":
            data = yaml.load(raw_data)

        elif self.get("type") == "csv":
            data = list(map(dict, comma.load(raw_data, force_header=True)))

        return data

    def _post_process(
            self,
            data: typing.Union[list, dict],
            vars: typing.Optional[typing.Dict[str, str]],
            alternate_emails: typing.Optional[typing.Dict[str, typing.List[str]]] = None,
    ) -> list:

        if alternate_emails is not None:
            # this is a feature to make sure that, when a user is known
            # with an alias, that alias can be prioritized (or deprioritized)
            # centrally through the `alternate_emails` mechanisms
            # { ...
            #     "user1@domain.com": ["user1@domain.com", "user1.alias@domain.com"],
            # ... }
            # => replace emails
            iterable = slacktivate.input.helpers.iterable_from_list_or_dict(data)
            for user_row in iterable:
                # only place where EMAIL_FIELD_NAME is needed
                email = user_row.get(EMAIL_FIELD_NAME)
                if email is None:
                    continue

                ae_lookup = alternate_emails.get(email)
                ae_lookup = ae_lookup or alternate_emails.get(email.lower())
                if ae_lookup is None:
                    continue

                # shouldn't happen but let's see
                if type(ae_lookup) is str:
                    ae_lookup = [ae_lookup]

                # ae_lookup should be a list
                if email not in ae_lookup:
                    ae_lookup += [email]

                user_row[EMAIL_FIELD_NAME] = ae_lookup[DEFAULT_EMAIL_INDEX]
                user_row[ALTERNATE_EMAIL_FIELD_NAME] = ae_lookup


        # the 'key' field is to reindex the database
        if "key" in self and self.get("key") is not None:

            key_pattern = self.get("key")

            # reindex data
            data = slacktivate.input.helpers.reindex_user_data(
                user_data=data,
                key=key_pattern,
            )
            iterable = slacktivate.input.helpers.iterable_from_list_or_dict(data)

            # store the key
            for record in iterable:
                record["key"] = key_pattern

        # create additional programmable fields
        if "fields" in self and self.get("fields") is not None:

            def __expand_record(record):
                new_fields = {}

                def formatter(pattern):
                    return slacktivate.input.helpers.render_jinja2(
                        jinja2_pattern=pattern,
                        data=record,
                        vars=vars,
                    )

                for field_name, field_pattern in self.get("fields").items():

                    if isinstance(field_pattern, str):
                        new_fields[field_name] = formatter(field_pattern)

                    elif isinstance(field_pattern, list):

                        # retrieve record's value for this field, if it exists
                        current_field_value = record.get(field_name, list())
                        if isinstance(current_field_value, str):
                            current_field_value = [current_field_value]

                        # format current field patterns:
                        new_values = list(map(formatter, field_pattern))

                        # assign field
                        new_fields[field_name] = current_field_value + new_values

                # new_fields = {
                #     field_name: slacktivate.input.helpers.render_jinja2(
                #         jinja2_pattern=field_pattern,
                #         data=record,
                #         vars=vars,
                #     )
                #     for field_name, field_pattern in self.get("fields").items()
                # }
                record.update(new_fields)
                return record

            if issubclass(type(data), list) or issubclass(type(data), collections.UserList):
                data = [
                    __expand_record(record)
                    for record in data
                ]

            if issubclass(type(data), dict) or issubclass(type(data), collections.UserDict):
                data = {
                    key: __expand_record(record)
                    for key, record in data.items()
                }

        # refilter data
        if "filter" in self and self.get("fields") is not None:
            data = slacktivate.input.helpers.refilter_user_data(
                user_data=data,
                filter_query=self.get("filter"),
                reindex=self.get("key") is not None,
            )

        return data

    def load(
            self,
            vars: typing.Optional[typing.Dict[str, str]],
            alternate_emails: typing.Optional[typing.Dict[str, typing.List[str]]] = None,
    ) -> list:
        data = self._load(vars=vars)
        data = self._post_process(data, vars=vars, alternate_emails=alternate_emails)
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
            users: typing.Union[list, dict],
            vars: typing.Optional[typing.Dict[str, str]],
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
                vars=vars,
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
            vars: typing.Optional[typing.Dict[str, str]],
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
                vars=vars,
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
        contents: typing.Optional[str] = None,
        filename: typing.Optional[str] = None,
) -> typing.Optional[dict]:
    if stream is not None:
        try:
            stream.seek(0)
        except io.UnsupportedOperation:
            pass
        contents = stream.read(),

    elif contents is not None:
        pass

    elif filename is not None and os.path.exists(filename):
        with open(filename, mode="r") as f:
            contents = f.read()

    else:
        # nothing is set
        raise ValueError(
            "no valid input source provided: "
            "stream, filename, contents all `None`"
        )

    obj = yaml.load(io.StringIO(contents), Loader=yaml.BaseLoader)

    return obj


class ParsingException(yaml.parser.ParserError):

    _EXCEPTION_MESSAGE_TEMPLATE = textwrap.dedent(
        """
        YAML parsing error: {{ context.context }}
          in "{{ context.context_mark.name }}", line {{ context.context_mark.line }}, column {{ context.context_mark.column }}
        {{ context.problem }}
          in "{{ context.problem_mark.name }}", line {{ context.problem_mark.line }}, column {{ context.problem_mark.column }}
        """)[1:]

    @property
    def filename(self):
        if "_filename" in self.__dict__:
            return self.__dict__.get("_filename")
        return self.context["context_mark"]["name"]

    @filename.setter
    def filename(self, value: str):
        self._filename = value

    @property
    def message(self):
        jinja_template = jinja2.Template(source=self._EXCEPTION_MESSAGE_TEMPLATE)
        data = slacktivate.helpers.dict_serializer.to_dict(self)

        def replace_key(obj, key, value):
            if issubclass(type(obj), dict):
                return {
                    _k: replace_key(_v, key, value) if _k != key else value
                    for (_k, _v) in obj.items()
                }
            return obj

        if self.filename is not None:
            data = replace_key(data, "name", self.filename)

        rendered_message = jinja_template.render(**data)

        return rendered_message


def parse_specification(
        stream: typing.Optional[io.TextIOBase] = None,
        contents: typing.Optional[str] = None,
        filename: typing.Optional[str] = None,
) -> typing.Optional[dict]:

    try:
        obj = _raw_parse_specification(
            stream=stream,
            contents=contents,
            filename=filename,
        )
    except yaml.parser.ParserError as exc:
        # will enhance message reporting
        new_exc = ParsingException(exc)
        if filename is not None:
            new_exc.filename = filename
        raise new_exc

    if "users" in obj:
        obj["users"] = list(map(UserSourceConfig, obj["users"]))

    if "groups" in obj:
        obj["groups"] = list(map(UserGroupConfig, obj["groups"]))

    if "channels" in obj:
        obj["channels"] = list(map(ChannelConfig, obj["channels"]))

    return obj
