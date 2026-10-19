"""`kitlib.records.record`: frozen dataclasses without importing `dataclasses` (plan 15, decision 120).

`dataclasses` imports `inspect`, ~40 ms on Windows, and every hook loads the config's classes on every
tool call. These tests pin the behaviour the kit's classes relied on from `@dataclass(frozen=True)`.
"""

import pytest

from kitlib.records import Factory, record


@record
class Point:
    x: int
    y: int = 0
    tags: list = Factory(list)


@record(order=True)
class Ordered:
    path: str
    line: int


@record
class Checked:
    value: int
    doubled: int = 0

    def __post_init__(self):
        object.__setattr__(self, "doubled", self.value * 2)


def test_positional_keyword_and_default_arguments():
    assert (Point(1).x, Point(1).y, Point(1, 2).y, Point(x=3, y=4).y) == (1, 0, 2, 4)


def test_a_factory_default_is_new_for_every_instance():
    first, second = Point(1), Point(1)
    first.tags.append("a")
    assert second.tags == []


def test_fields_are_frozen():
    point = Point(1)
    with pytest.raises(AttributeError):
        point.x = 2
    with pytest.raises(AttributeError):
        del point.x


def test_equality_and_hash_by_value_and_class():
    assert Point(1, 2) == Point(1, 2)
    assert Point(1, 2) != Point(1, 3)
    assert Point(1, 2) != (1, 2, [])  # not a tuple
    assert hash(Ordered("a", 1)) == hash(Ordered("a", 1))


def test_order_compares_fields_in_order():
    assert sorted([Ordered("b", 1), Ordered("a", 2), Ordered("a", 1)]) == [
        Ordered("a", 1),
        Ordered("a", 2),
        Ordered("b", 1),
    ]
    with pytest.raises(TypeError):
        Point(1) < Point(2)  # noqa: B015 - unordered records refuse, as dataclasses do


def test_post_init_runs():
    assert Checked(3).doubled == 6


def test_repr_names_the_fields():
    assert repr(Point(1, 2)) == "Point(x=1, y=2, tags=[])"


@pytest.mark.parametrize(
    "args, kwargs",
    [((), {}), ((1, 2, [], 4), {}), ((1,), {"x": 2}), ((1,), {"z": 2})],
)
def test_wrong_arguments_are_a_type_error(args, kwargs):
    with pytest.raises(TypeError):
        Point(*args, **kwargs)


def test_field_names_are_listed():
    assert Point._fields == ("x", "y", "tags")


def test_a_required_field_after_a_default_is_refused():
    with pytest.raises(TypeError):

        @record
        class Bad:
            x: int = 0
            y: int


def test_field_names_the_generated_code_might_use():
    # Review round 2: the generated __init__'s own names must not collide with a field's.
    @record
    class Odd:
        self: int
        _set: int = 0
        _MISSING: list = Factory(list)

    odd = Odd(1, 2)
    assert (odd.self, odd._set, odd._MISSING) == (1, 2, [])
