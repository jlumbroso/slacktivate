
import typing


__author__ = "Jérémie Lumbroso <lumbroso@cs.princeton.edu>"

__all__ = [
    "first_or_none",
]


# type variable
_alpha = typing.TypeVar("_alpha")


def first_or_none(
        lst: typing.Union[None, typing.List[_alpha], typing.Iterable[_alpha]]
) -> typing.Optional[_alpha]:
    """
    Returns the first element of a list-like or iterable value :py:data:`lst`, or `None`
    if the value is `None` or not a list.

    :param lst: A list-like or iterable value or ``None``
    :type lst: Optional[List[_alpha]]

    :return: The first element if it can be extracted, otherwise ``None``
    """

    # let's try as a list-like object first
    try:
        if lst is None or len(lst) == 0:
            return
        return lst[0]
    except TypeError:
        # - will be thrown if len(X) on an object that can't provide a length
        # - will be thrown if X[0] on an object that can't be subscripted
        pass

    # let's try as an iterator
    try:
        for item in lst:
            return item
    except TypeError:
        # - will throw an exception if X is not iterable
        return
