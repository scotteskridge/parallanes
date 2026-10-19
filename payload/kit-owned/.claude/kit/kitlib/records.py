"""Frozen record classes, as `@dataclass(frozen=True)` makes them, without importing `dataclasses`.

`dataclasses` imports `inspect` (~40 ms on Windows), and the hooks load the config's classes on every
tool call (decision 120). Only what the kit uses: fields from annotations, defaults, `Factory`
defaults, `__post_init__`, frozen attributes, equality, hashing and optional ordering. Like
dataclasses, `__init__` and the field tuple are generated as code for each class: a generic
`__init__` made `lane_owners.overlaps` on 100,000 files a third slower.
"""

import operator


class Factory:
    """A default made fresh for each instance, like `field(default_factory=...)`."""

    def __init__(self, make):
        self.make = make


_MISSING = object()


def record(cls=None, *, order: bool = False):
    """Use as `@record` or `@record(order=True)`."""
    if cls is None:
        return lambda cls: _build(cls, order)
    return _build(cls, order)


def _build(cls, order: bool):
    # Not cls.__dict__["__annotations__"]: from Python 3.14 annotations are made on first access
    # (PEP 649). That access evaluates them, so a field's annotation must name something already
    # defined (dataclasses would accept a forward reference): at import, every hook would fail.
    names = tuple(cls.__annotations__)
    for name in names:
        if not name.isidentifier():
            raise TypeError(f"{cls.__name__}: field {name!r} is not an identifier")
    scope = {"__record_set": object.__setattr__, "__record_missing": _MISSING}
    params, body = [], []
    for name in names:
        default = cls.__dict__.get(name, _MISSING)
        if default is _MISSING:
            if params and "=" in params[-1]:
                raise TypeError(f"{cls.__name__}: field {name!r} without a default follows one with a default")
            params.append(name)
        elif isinstance(default, Factory):
            delattr(cls, name)  # the instance always has its own value
            scope[f"__record_make_{name}"] = default.make
            params.append(f"{name}=__record_missing")
            body.append(f"    if {name} is __record_missing:\n        {name} = __record_make_{name}()")
        else:
            scope[f"__record_default_{name}"] = default
            params.append(f"{name}=__record_default_{name}")
        body.append(f"    __record_set(__record_self, {name!r}, {name})")
    if hasattr(cls, "__post_init__"):
        body.append("    __record_self.__post_init__()")
    fields = "".join(f"self.{name}, " for name in names)
    source = (
        f"def __init__(__record_self, {', '.join(params)}):\n" + "\n".join(body or ["    pass"]) + "\n"
        f"def _values(self):\n    return ({fields})\n"
    )
    exec(source, scope)  # built only from the class's own field names, checked as identifiers above
    _values = scope["_values"]

    def __repr__(self):
        return f"{cls.__name__}({', '.join(f'{name}={getattr(self, name)!r}' for name in names)})"

    def __eq__(self, other):
        return _values(self) == _values(other) if other.__class__ is self.__class__ else NotImplemented

    def __hash__(self):
        return hash(_values(self))

    def __setattr__(self, name, value):
        raise AttributeError(f"cannot assign to field {name!r}: {cls.__name__} is frozen")

    def __delattr__(self, name):
        raise AttributeError(f"cannot delete field {name!r}: {cls.__name__} is frozen")

    methods = {
        "__init__": scope["__init__"],
        "__repr__": __repr__,
        "__eq__": __eq__,
        "__hash__": __hash__,
        "__setattr__": __setattr__,
        "__delattr__": __delattr__,
    }
    if order:
        for name, compare in (
            ("__lt__", operator.lt),
            ("__le__", operator.le),
            ("__gt__", operator.gt),
            ("__ge__", operator.ge),
        ):
            methods[name] = _comparison(compare, _values)
    for name, method in methods.items():
        method.__qualname__ = f"{cls.__qualname__}.{name}"
        setattr(cls, name, method)
    cls._fields = names
    return cls


def _comparison(compare, values):
    def method(self, other):
        return compare(values(self), values(other)) if other.__class__ is self.__class__ else NotImplemented

    return method
