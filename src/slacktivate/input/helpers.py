
import collections
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
        data: typing.Optional[typing.Union[list, dict]],
) -> str:

    if type(data) is None:
        return jinja2.Template(jinja2_pattern).render()

    if issubclass(type(data), list) or issubclass(type(data), collections.UserList):
        return jinja2.Template(jinja2_pattern).render(
            record=data, *data,
        )

    if issubclass(type(data), dict) or issubclass(type(data), collections.UserDict):
        return jinja2.Template(jinja2_pattern).render(
            record=list(data.values()), **data,
        )
