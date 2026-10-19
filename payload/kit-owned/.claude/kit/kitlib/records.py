"""Frozen record classes, as `@dataclass(frozen=True)` makes them, without importing `dataclasses`.

`dataclasses` imports `inspect` (~40 ms on Windows), and the hooks load the config's classes on every
tool call (decision 120). Only what the kit uses: fields from annotations, defaults, `Factory`
defaults, `__post_init__`, frozen attributes, equality, hashing and optional ordering.
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
    # Not cls.__dict__["__annotations__"]: from Python 3.14 annotations are made on first access (PEP 649).
    names = tuple(cls.__annotations__)
    defaults = []
    for name in names:
        default = cls.__dict__.get(name, _MISSING)
        if default is _MISSING and any(d is not _MISSING for d in defaults):
            raise TypeError(f"{cls.__name__}: field {name!r} without a default follows one with a default")
        defaults.append(default)
        if isinstance(default, Factory):
            delattr(cls, name)  # the instance always has its own value
    post_init = getattr(cls, "__post_init__", None)

    def __init__(self, *args, **kwargs):
        if len(args) > len(names):
            raise TypeError(f"{cls.__name__}() takes {len(names)} arguments, {len(args)} given")
        values = dict(zip(names, args, strict=False))
        for name, value in kwargs.items():
            if name not in names:
                raise TypeError(f"{cls.__name__}() got an unexpected argument {name!r}")
            if name in values:
                raise TypeError(f"{cls.__name__}() got {name!r} twice")
            values[name] = value
        for name, default in zip(names, defaults, strict=True):
            if name not in values:
                if default is _MISSING:
                    raise TypeError(f"{cls.__name__}() missing argument {name!r}")
                values[name] = default.make() if isinstance(default, Factory) else default
            object.__setattr__(self, name, values[name])
        if post_init is not None:
            post_init(self)

    def _values(self):
        return tuple(getattr(self, name) for name in names)

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
        "__init__": __init__,
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
