
import typing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "to_dict",
    "to_flat_dict",
    "dict_to_flat_dict",
]


_ELEMENTARY_TYPE: typing.List[typing.Type] = [int, str, float, bool, type(None)]


def _is_elementary_type(obj: typing.Any) -> bool:
    for typ in _ELEMENTARY_TYPE:
        if issubclass(type(obj), typ):
            return True
    return False


def to_dict(
        obj: typing.Any
) -> typing.Union[typing.List, typing.Dict[str, typing.Any]]:
    if _is_elementary_type(obj):
        return obj

    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        return {
            key: to_dict(value)
            for (key, value) in obj.items()
        }

    return to_dict(obj.__dict__)


def dict_to_flat_dict(
        dict_obj: typing.Dict[str, typing.Any],
) -> typing.Dict[str, typing.Any]:

    result = dict()

    def _aux(
            dict_obj: typing.Dict[str, typing.Any],
            prefix: typing.Optional[str] = None,
    ) -> typing.NoReturn:
        prefix = prefix if prefix is not None else ""

        for (key, value) in dict_obj.items():
            path ="{prefix}.{key}".format(
                prefix=prefix,
                key=key,
            ).strip(".")

            if isinstance(value, dict):
                _aux(
                    dict_obj=value,
                    prefix=path,
                )

            else:
                result[path] = value

    _aux(dict_obj=dict_obj)

    return result


def to_flat_dict(obj: typing.Any) -> typing.Dict[str, typing.Any]:
    return dict_to_flat_dict(
        dict_obj=to_dict(obj),
    )


def add_missing_dict_fields(
        list_of_dicts: typing.List[typing.Dict[typing.Any, typing.Any]],
) -> typing.List[typing.Dict[typing.Any, typing.Any]]:

    fields = list()

    for d in list_of_dicts:
        for field in d.keys():
            if field in fields:
                continue
            fields.append(field)

    list_of_dicts_with_missing_fields = [
        {
            field: d.get(field, "")
            for field in fields
        }
        for d in list_of_dicts
    ]

    return list_of_dicts_with_missing_fields
