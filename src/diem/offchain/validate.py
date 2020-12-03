# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

"""This package provides validation functions for offchain data"""

from .types import PaymentObject
from .error import invalid_request
from .role import Role
from .payment_state import MACHINE as payment_machine, summary, trigger_role

import typing


def inbound_payment(new_payment: PaymentObject, event_role: Role, current: typing.Optional[PaymentObject]) -> None:
    # 1. validate payment does not change fields that should be set only once
    # todo

    # 2. validate op can perform new payment state
    try:
        new_state = payment_machine.match_state(new_payment)
    except ValueError as e:
        # todo: test
        raise invalid_request(f"new payment object({summary(new_payment)}) does not match any valid states")

    expected_role = trigger_role(new_state)
    if event_role != expected_role:
        raise invalid_request(
            f"payment({summary(new_payment)}) is expected from {expected_role}, but from {event_role}"
        )

    # 3. validate payment state is a valid transition result
    if current:
        state = payment_machine.match_state(current)
        if not payment_machine.is_valid_transition(state, new_state, new_payment):
            raise invalid_request(f"can not transit payment({summary(new_payment)}) from {summary(current)}")
    else:
        # 4. validate payment state is correct initial state data if current payment is none
        if not payment_machine.is_initial(new_state):
            raise invalid_request(f"invalid initial payment({summary(new_payment)})")
