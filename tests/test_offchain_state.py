# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem.offchain.state import (
    State,
    build_machine,
    new_transition,
    require,
    field,
    value,
    TooManyStatesMatchedError,
    NoStateMatchedError,
)
import dataclasses, pytest, typing


@dataclasses.dataclass
class Object:
    a: typing.Optional[str] = dataclasses.field(default=None)
    b: typing.Optional["Object"] = dataclasses.field(default=None)
    c: typing.Optional["Object"] = dataclasses.field(default=None)


def test_state():
    a = State(id="a")
    b = State(id="b", require=require(field("b")))
    c = State(id="c", require=require(value("b.a", "world")))
    d = State(id="d", require=require(field("b"), field("c")))

    o = Object(a="hello", b=Object(a="world", c=Object("!")))
    assert a.match(o)
    assert b.match(o)
    assert c.match(o)
    assert not d.match(o)
    assert d.match(Object(a="hello", b=Object(a="world"), c=Object("!")))


def test_build_machine():
    a = State(id="a", require=require(field("a")))
    b = State(id="b", require=require(field("b")))
    c = State(id="c", require=require(field("c")))
    d = State(id="d", require=require(value("c.b.a", "world")))

    transitions = [
        new_transition(a, b),
        new_transition(b, c, require(field("b.c"))),
        new_transition(c, d, require(value("b.c.a", "hello"))),
        new_transition(c, c, require(field("c.b.a"))),
    ]
    m = build_machine(transitions)
    assert m.initials == [a]

    assert len(m.states) == 4
    assert a in m.states
    assert b in m.states
    assert c in m.states
    assert d in m.states

    assert m.transitions == transitions


def test_match_states_by_context_object_field():
    a = State(id="a", require=require(field("a")))
    b = State(id="b", require=require(field("b", not_set=False)))
    c = State(id="c", require=require(field("c", not_set=True)))

    m = build_machine(
        [
            new_transition(a, b),
            new_transition(a, c),
        ]
    )
    assert m.match_states(Object(a="hello")) == [a, c]
    assert m.match_states(Object(a="hello", c=Object())) == [a]
    assert m.match_states(Object(b=Object())) == [b, c]
    assert m.match_states(Object(a="hello", b=Object())) == [a, b, c]
    assert m.match_states(Object(c=None)) == [c]
    assert m.match_states(Object(c=Object())) == []

    assert m.explain_match_states(Object(a="hello"))


def test_match_states_by_context_object_field_value():
    a = State(id="a", require=require(value("a", "hello")))
    b = State(id="b", require=require(value("b.a", "hello")))

    m = build_machine(
        [
            new_transition(a, b),
        ]
    )
    assert m.match_states(Object(a="hello")) == [a]
    assert m.match_states(Object(a="world", b=Object(a="hello"))) == [b]
    assert m.match_states(Object(a="hello", c=Object())) == [a]


def test_match_state_returns_exact_one_matched_state():
    a = State(id="a", require=require(value("a", "hello")))
    b = State(id="b", require=require(field("b")))

    m = build_machine(
        [
            new_transition(a, b),
        ]
    )

    assert m.match_state(Object(a="hello")) == a
    assert m.match_states(Object(a="hello", b=Object())) == [a, b]

    # multi match
    with pytest.raises(TooManyStatesMatchedError):
        assert m.match_state(Object(a="hello", b=Object()))
    # no match
    with pytest.raises(NoStateMatchedError):
        assert m.match_state(Object(a="world"))


def test_is_initial():
    a = State(id="a", require=require(field("a")))
    b = State(id="b", require=require(field("b")))

    m = build_machine(
        [
            new_transition(a, b),
        ]
    )
    assert m.is_initial(m.match_state(Object(a="hello")))
    m.is_initial(m.match_state(Object(b=Object())))


def test_is_valid():
    a = State(id="a", require=require(field("a")))
    b = State(id="b", require=require(field("b")))
    c = State(id="c", require=require(field("c")))

    m = build_machine(
        [
            new_transition(a, b),
            new_transition(b, c, require(field("b.a"))),
        ]
    )
    assert m.is_valid_transition(a, b, None)
    assert m.is_valid_transition(a, b, Object())
    assert m.is_valid_transition(a, b, Object(a="any"))
    assert not m.is_valid_transition(b, c, Object())
    assert not m.is_valid_transition(b, c, None)
    assert m.is_valid_transition(b, c, Object(b=Object(a="hello")))
