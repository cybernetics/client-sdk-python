# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses, typing, abc


S = typing.TypeVar("S")
T = typing.TypeVar("T")


class Condition(abc.ABC, typing.Generic[T]):
    @abc.abstractmethod
    def match(self, event_data: T) -> bool:
        ...

    def explain(self, event_data: T) -> str:
        ret = "match" if self.match(event_data) else "not match"
        return f"{self}: {ret}"


@dataclasses.dataclass(frozen=True)
class Field(Condition[T]):
    path: str
    not_set: bool

    def match(self, event_data: T) -> bool:
        val = event_data
        for f in self.path.split("."):
            if val is None or not hasattr(val, f):
                return False
            val = getattr(val, f)

        if self.not_set:
            return val is None
        return val is not None


@dataclasses.dataclass(frozen=True)
class Value(Condition[T], typing.Generic[T, S]):
    path: str
    value: S

    def match(self, event_data: T) -> bool:
        val = event_data
        for f in self.path.split("."):
            if val is None or not hasattr(val, f):
                return False
            val = getattr(val, f)
        return val == self.value


@dataclasses.dataclass(frozen=True)
class Require(Condition[T]):
    conds: typing.List[Condition[T]]

    def match(self, event_data: T) -> bool:
        for cond in self.conds:
            if not cond.match(event_data):
                return False

        return True

    def explain(self, event_data: T) -> str:
        return "require:\n" + "\n".join([cond.explain(event_data) for cond in self.conds])

    def __hash__(self) -> int:
        return hash(tuple(self.conds))


@dataclasses.dataclass(frozen=True)
class State(typing.Generic[T]):
    id: str
    require: typing.Optional[Require[T]] = dataclasses.field(default=None)

    def match(self, event_data: T) -> bool:
        if self.require:
            return self.require.match(event_data)
        return True

    def __str__(self) -> str:
        return self.id

    def explain(self, event_data: T) -> str:
        require_explain = self.require.explain(event_data) if self.require else "match"
        return f"---- state({self.id}) ----\n{require_explain}"


@dataclasses.dataclass(frozen=True)
class Transition(typing.Generic[T]):
    action: str
    state: State[T]
    to: State[T]
    condition: typing.Optional[Condition[T]]


class NoStateMatchedError(ValueError):
    pass


class TooManyStatesMatchedError(ValueError):
    pass


@dataclasses.dataclass
class Machine(typing.Generic[T]):
    initials: typing.List[State[T]]
    states: typing.List[State[T]]
    transitions: typing.List[Transition[T]]

    def is_initial(self, state: State[T]) -> bool:
        return state in self.initials

    def is_valid_transition(self, state: State[T], to: State[T], event_data: T) -> bool:
        for t in self.transitions:
            if t.state == state and t.to == to:
                if t.condition:
                    return t.condition.match(event_data)
                return True
        return False

    def match_state(self, event_data: T) -> State[T]:
        ret = self.match_states(event_data)
        if not ret:
            raise NoStateMatchedError(f"could not find state matches given event data({event_data})")
        if len(ret) > 1:
            raise TooManyStatesMatchedError(f"found multiple states({ret}) match given event data({event_data})")
        return ret[0]

    def match_states(self, event_data: T) -> typing.List[State[T]]:
        return [state for state in self.states if state.match(event_data)]

    def explain_match_states(self, event_data: T) -> str:
        return "\n".join([state.explain(event_data) for state in self.states if state.require])


def new_transition(state: State[T], to: State[T], cond: typing.Optional[Condition[T]] = None) -> Transition[T]:
    return Transition(action=f"{state} -> {to}", state=state, to=to, condition=cond)


def require(*args: Condition[T]) -> Require[T]:
    return Require(conds=list(args))


def field(path: str, not_set: bool = False, _: T = None) -> Field[T]:
    return Field(path=path, not_set=not_set)


def value(path: str, value: S, _: T = None) -> Value[T, S]:
    return Value(path=path, value=value)


def build_machine(transitions: typing.List[Transition[T]]) -> Machine[T]:
    states = {}
    tos = {}
    for t in transitions:
        states[t.state.id] = t.state
        states[t.to.id] = t.to
        tos[t.to.id] = t.to

    initial_ids = set(states.keys()) - set(tos.keys())
    return Machine(initials=[states[id] for id in initial_ids], states=list(states.values()), transitions=transitions)
