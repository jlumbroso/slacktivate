
import collections
import copy
import typing

import jinja2
import yaql
import yaql.language.exceptions


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "flatten",
    "parseable_yaql",
    "parseable_jinja2",
    "find_jinja2_template_fields",
]


def flatten(
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


def iterable_from_list_or_dict(data: typing.Union[list, dict]) -> typing.Iterable:
    iterable = None
    if type(data) is list:
        iterable = data
    elif type(dict) is dict:
        iterable = data.values()
    else:
        # heuristic by
        # Easier to Ask for Forgiveness than Permission
        try:
            # assume it's a dict
            iterable = data.values()
        except AttributeError:
            try:
                # assume it's a list
                iterable = list(data)
            except TypeError as exc:
                raise Exception(
                    "unable to process data: <{}> {}".format(type(data), data),
                ) from exc
    
    if iterable is None:
        raise Exception("unable to process data: <{}> {}".format(type(data), data))
    
    return iterable


def merge_dict(
        src: typing.Optional[dict] = None,
        dest: typing.Optional[dict] = None,
        only_exact_merge: bool = False,
) -> typing.Optional[dict]:

    # edge cases
    if src is None:
        return dest
    if dest is None:
        return src

    result = copy.deepcopy(src)
    for (key, value) in dest.items():

        # easy: new field
        if key not in result:
            result[key] = value
            continue

        # type list
        if type(value) is list and type(result[key]) is list:

            # concatenate results
            l = result[key]
            for v in value:
                if v not in l:
                    l.append(v)
            result[key] = l

        else:

            if only_exact_merge:
                if result[key] != value:
                    raise ValueError(
                        "merging the same user from different sources, conflict on {}".format(key)
                    )

            # override
            result[key] = value

    return result


def parseable_jinja2(s: str) -> bool:
    try:
        jinja2.Template(s).render()
    except jinja2.TemplateSyntaxError:
        return False

    return True


def parseable_yaql(s: str) -> bool:
    try:
        engine = yaql.factory.YaqlFactory().create()
        engine(s)
    except yaql.language.exceptions.YaqlGrammarException:
        return False
    except yaql.language.exceptions.YaqlLexicalException:
        return False
    except yaql.language.exceptions.YaqlParsingException:
        return False

    return True


def find_jinja2_template_fields(
        jinja2_pattern: str
) -> typing.List[str]:
    fields = []

    # environment where missing fields raise exception

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)

    # since only raise exception for one name at a time,
    # iterate, and substitute all known fields by an empty
    # string

    while True:
        try:
            env.from_string(jinja2_pattern).render(
                **{ field: "" for field in fields})
        except jinja2.exceptions.UndefinedError as exc:
            if "' is undefined" not in exc.message:
                break
            missing_field = exc.message.split("'")[1]
            fields.append(missing_field)
            continue
        break

    return fields


def render_jinja2(
        jinja2_pattern: str,
        data: typing.Optional[typing.Union[list, dict]] = None,
        vars: typing.Optional[typing.Dict[str, str]] = None,
) -> str:

    if vars is None:
        vars = dict()

    if data is None or type(data) is None:
        return jinja2.Template(jinja2_pattern).render(vars=vars)

    if issubclass(type(data), list) or issubclass(type(data), collections.UserList):
        return jinja2.Template(jinja2_pattern).render(
            record=data, vars=vars, *data,
        )

    if issubclass(type(data), dict) or issubclass(type(data), collections.UserDict):
        return jinja2.Template(jinja2_pattern).render(
            record=list(data.values()), vars=vars, **data,
        )


def unindex_data(data: typing.Union[list, dict]) -> list:
    if issubclass(type(data), dict) or issubclass(type(data), collections.UserDict):
        data = list(data.values())

    return data


def reindex_user_data(
        user_data: typing.Union[list, dict],
        key: typing.Optional[str] = None,
        unmodify_default: bool = True
) -> dict:

    key_pattern = key

    # reindex according to key
    def pick_key_pattern(record):
        if key_pattern is not None:
            return key_pattern

        if issubclass(type(record), dict) or issubclass(type(record), collections.UserDict):
            if record.get("key") is not None:
                return record.get("key")

            for key, value in record.items():
                if "@" in value:
                    return "{{{{ {} }}}}".format(key)

            return "{{{{ {} }}}}".format(list(record.values())[0])

        if issubclass(type(record), list) or issubclass(type(record), collections.UserList):
            return "{{ data[0] }}"

        if unmodify_default:
            return  # default to None

        return "{{ data }}"

    def pick_key(record):
        return render_jinja2(
            jinja2_pattern=pick_key_pattern(record=record),
            data=record,
        )

    reindexed_user_data = {
        pick_key(record): record
        for record in unindex_data(data=user_data)
    }

    # if None is a key, then return original data
    if None not in reindexed_user_data:
        return reindexed_user_data

    return user_data


def refilter_user_data(
        user_data: typing.Union[list, dict],
        filter_query: typing.Optional[str] = None,
        reindex: bool = True,
        key: typing.Optional[str] = None,
) -> typing.Union[list, dict]:

    user_data = unindex_data(data=user_data)

    # NOTE: should catch exceptions from Yaql for better error reporting
    engine = yaql.factory.YaqlFactory().create()
    expression = engine(filter_query)
    filtered_user_data = expression.evaluate(data=user_data)

    if reindex:
        filtered_user_data = reindex_user_data(
            user_data=filtered_user_data,
            key=key,
            unmodify_default=True,
        )

    return filtered_user_data


def deduplicate_user_data(
        user_data: typing.Union[list, dict],
        key: typing.Optional[str] = None,
) -> dict:

    if issubclass(type(user_data), dict) or issubclass(type(user_data), collections.UserDict):
        # should already not have duplicates
        # but reindexing according to user-specified key if provided
        if key is not None:
            user_data = reindex_user_data(
                user_data=user_data,
                key=key,
            )

    elif issubclass(type(user_data), list) or issubclass(type(user_data), collections.UserList):

        if key is not None:
            # reindex data according to key then return unindexed
            user_data = reindex_user_data(
                user_data=user_data,
                key=key,
            )
            user_data = unindex_data(user_data)

        else:
            user_data = reindex_user_data(
                user_data=user_data,
            )
            user_data = unindex_data(user_data)
            # # sort and eliminate duplicates
            # user_data = sorted(user_data, key=dict)
            # user_data = [
            #     user_data[i]
            #     for i in range(len(user_data))
            #     if user_data[i-1] != user_data[i]
            # ]

    return user_data
