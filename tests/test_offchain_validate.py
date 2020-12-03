# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem.offchain import types, Role, individual_kyc_data, validate, Error, update_payment
import pytest


@pytest.fixture
def initial_payment(factory):
    return factory.new_payment_command_request().command.payment


def test_validate_initial_payment(initial_payment):
    validate.inbound_payment(initial_payment, Role.SENDER, None)


def test_invalid_payment_trigger_role(initial_payment):
    with pytest.raises(Error):
        validate.inbound_payment(initial_payment, Role.RECEIVER, None)


def test_validate_inbound_payment_from_sinit_to_rsend(initial_payment):
    receiver_ready = update_payment(
        Role.RECEIVER,
        initial_payment,
        status=types.Status.ready_for_settlement,
        kyc_data=individual_kyc_data(given_name="Rose"),
        recipient_signature="signature",
    )

    validate.inbound_payment(receiver_ready, Role.RECEIVER, initial_payment)


def test_validate_inbound_payment_path_receiver_soft_match(initial_payment):
    receiver_soft_match = update_payment(
        Role.RECEIVER,
        initial_payment,
        status=types.Status.soft_match,
    )

    validate.inbound_payment(receiver_soft_match, Role.RECEIVER, initial_payment)

    sender_soft_send = update_payment(Role.SENDER, receiver_soft_match, additional_kyc_data="additional_kyc_data")
    validate.inbound_payment(sender_soft_send, Role.SENDER, receiver_soft_match)

    receiver_ready = update_payment(
        Role.RECEIVER,
        sender_soft_send,
        status=types.Status.ready_for_settlement,
        kyc_data=individual_kyc_data(given_name="Rose"),
        recipient_signature="signature",
    )
    validate.inbound_payment(receiver_ready, Role.RECEIVER, sender_soft_send)
