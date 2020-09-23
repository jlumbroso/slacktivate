
import typing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "to_dict",
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
