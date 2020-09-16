
import typing

import jinja2


def find_jinja2_template_fields(jinja2_pattern: str) -> typing.List[str]:
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
