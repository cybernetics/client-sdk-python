# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

""" This package provides data structures and utilities for implementing Diem Offchain API Service.

See [Diem Offchain API](https://dip.diem.com/lip-1/) for more details.

"""

from .types import (
    CommandType,
    CommandResponseStatus,
    OffChainErrorType,
    OffChainErrorAbortCode,
    Command,
    CommandRequestObject,
    CommandResponseObject,
    OffChainErrorObject,
    PaymentObject,
    PaymentActorObject,
    PaymentActionObject,
    Status,
    StatusObject,
    KycDataObjectType,
    NationalIdObject,
    AddressObject,
    KycDataObject,
    init_payment_request,
    new_payment_request,
    reply_request,
    individual_kyc_data,
    entity_kyc_data,
    to_json,
    from_json,
)
from .http_header import X_REQUEST_ID
from .error import protocol_error, command_error, invalid_request, Error
from .role import Action, Role
from .client import Client

from . import jws, http_server, state, payment_state, validate
from .. import identifier, txnmetadata

import typing, dataclasses


def follow_up_action(role: Role, payment: PaymentObject) -> typing.Optional[Action]:
    state = payment_state.MACHINE.match_state(payment)
    return payment_state.follow_up_action(role, state)


def travel_rule_metadata(payment: PaymentObject, hrp: str) -> typing.Tuple[bytes, bytes]:
    address, _ = identifier.decode_account(payment.sender.address, hrp)
    return txnmetadata.travel_rule(payment.reference_id, address, payment.action.amount)


def update_payment_request(*args, **kwargs) -> CommandRequestObject:
    return new_payment_request(update_payment(*args, **kwargs))


def update_payment(
    role: Role,
    payment: PaymentObject,
    recipient_signature: typing.Optional[str] = None,
    status: typing.Optional[Status] = None,
    kyc_data: typing.Optional[KycDataObject] = None,
    additional_kyc_data: typing.Optional[str] = None,
    abort_code: typing.Optional[str] = None,
    abort_message: typing.Optional[str] = None,
) -> PaymentObject:
    new_recipient_signature = recipient_signature or payment.recipient_signature
    actor = role.payment_actor(payment)
    changes = {
        role.value: update_payment_actor(
            actor,
            status=status,
            kyc_data=kyc_data,
            additional_kyc_data=additional_kyc_data,
            abort_code=abort_code,
            abort_message=abort_message,
        ),
        "recipient_signature": new_recipient_signature,
    }
    return dataclasses.replace(payment, **changes)


def update_payment_actor(
    actor: PaymentActionObject,
    status: typing.Optional[Status] = None,
    kyc_data: typing.Optional[KycDataObject] = None,
    additional_kyc_data: typing.Optional[str] = None,
    abort_code: typing.Optional[str] = None,
    abort_message: typing.Optional[str] = None,
) -> PaymentActionObject:
    new_status = StatusObject(
        status=status or actor.status.status,
        abort_code=abort_code,
        abort_message=abort_message,
    )
    new_kyc_data = kyc_data or actor.kyc_data
    if additional_kyc_data:
        new_kyc_data = dataclasses.replace(new_kyc_data, additional_kyc_data=additional_kyc_data)

    return dataclasses.replace(actor, kyc_data=new_kyc_data, status=new_status)
