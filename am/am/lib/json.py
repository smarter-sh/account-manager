"""
Overridden JSON utilities.

The effective modifications are

- Use :class:`AMJSONEncoder` (Django's ``DjangoJSONEncoder``) as the default encoder
- Standardize indentation to 2 characters
- Use ``str`` for objects that the encoder can't otherwise serialize
"""

import json
from json import JSONDecodeError, load, loads  # noqa: F401 unmodified re-export

from django.core.serializers.json import DjangoJSONEncoder


class AMJSONEncoder(DjangoJSONEncoder):
    """
    Django's JSON encoder, which knows date/time, decimal, UUID and lazy translation.

    types, falling back to ``str()`` for any other object.
    """

    def default(self, o):
        """
        Serialize an object that the json module can't serialize by itself.

        :param o: The object.
        :returns: Its JSON-serializable representation.
        """
        try:
            return super().default(o)
        except TypeError:
            return str(o)


def dumps(
    obj,
    *,
    skipkeys=False,
    ensure_ascii=True,
    check_circular=True,
    allow_nan=True,
    cls=None,
    indent=None,
    separators=None,
    default=None,
    sort_keys=False,
    **kw,
):
    """
    JSON dump with.

    - :class:`AMJSONEncoder` as default encoder
    - indent of 2
    - ``str`` for otherwise non-serializable objects, unless ``default`` is given

    The arguments are those of :func:`json.dumps`.

    :returns: The JSON string.
    """
    return json.dumps(
        obj,
        skipkeys=skipkeys,
        ensure_ascii=ensure_ascii,
        check_circular=check_circular,
        allow_nan=allow_nan,
        cls=cls or AMJSONEncoder,
        indent=indent or 2,
        separators=separators,
        default=default,
        sort_keys=sort_keys,
        **kw,
    )
