# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem.offchain import payment_state, types, Role, Action, individual_kyc_data, update_payment
import pytest


def test_state_machine(factory):
    m = payment_state.MACHINE
    payment = factory.new_payment_command_request().command.payment

    initial_state = m.match_state(payment)
    assert initial_state
    assert m.is_initial(initial_state)
    assert payment_state.S_INIT == initial_state

    with pytest.raises(ValueError):
        m.match_state(update_payment(Role.RECEIVER, payment, status=types.Status.ready_for_settlement))

    receiver_ready_payment = update_payment(
        Role.RECEIVER,
        payment,
        status=types.Status.ready_for_settlement,
        kyc_data=individual_kyc_data(given_name="Rose"),
        recipient_signature="signature",
    )
    receiver_ready = m.match_state(receiver_ready_payment)
    assert receiver_ready == payment_state.R_SEND
    assert m.is_valid_transition(initial_state, receiver_ready, receiver_ready_payment)


def test_follow_up_action():
    assert payment_state.follow_up_action(Role.RECEIVER, payment_state.S_INIT) == Action.EVALUATE_KYC_DATA
    assert payment_state.follow_up_action(Role.SENDER, payment_state.R_SEND) == Action.EVALUATE_KYC_DATA
    assert payment_state.follow_up_action(Role.RECEIVER, payment_state.R_SEND) == None
    assert payment_state.follow_up_action(Role.SENDER, payment_state.R_ABORT) == None
    assert payment_state.follow_up_action(Role.RECEIVER, payment_state.R_ABORT) == None
