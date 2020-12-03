# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .data_types import (
    NationalIdObject,
    AddressObject,
    OffChainErrorType,
    OffChainErrorAbortCode,
    KycDataObjectType,
    Status,
    StatusObject,
    PaymentObject,
    PaymentActorObject,
    PaymentActionObject,
    KycDataObject,
    KycDataObjectType,
    CommandType,
    CommandRequestObject,
    CommandResponseObject,
    Command,
    OffChainErrorObject,
    CommandResponseStatus,
)
from . import schema

import secrets, typing, uuid


T = typing.TypeVar("T")


def to_json(obj: T, indent: typing.Optional[int] = None) -> str:
    schema_class = getattr(schema, type(obj).__name__)
    return schema_class().dumps(obj, indent=indent)


def from_json(data: str, klass: typing.Type[T]) -> T:
    schema_class = getattr(schema, klass.__name__)
    return schema_class().loads(data)


def init_payment_request(
    sender_account_id: str,
    sender_kyc_data: KycDataObject,
    receiver_account_id: str,
    amount: int,
    currency: str,
) -> CommandRequestObject:
    """Initialize a payment request command

    returns generated reference_id and created `CommandRequestObject`
    """
    cid = secrets.token_hex(16)

    reference_id = uuid.uuid1().hex

    return CommandRequestObject(
        cid=cid,
        command_type=CommandType.PaymentCommand,
        command=Command(
            _ObjectType=CommandType.PaymentCommand,
            payment=PaymentObject(
                reference_id=reference_id,
                sender=PaymentActorObject(
                    address=sender_account_id,
                    kyc_data=sender_kyc_data,
                    status=StatusObject(status=Status.needs_kyc_data),
                ),
                receiver=PaymentActorObject(
                    address=receiver_account_id,
                    status=StatusObject(status=Status.none),
                ),
                action=PaymentActionObject(amount=amount, currency=currency),
            ),
        ),
    )


def new_payment_request(
    payment: PaymentObject,
    cid: typing.Optional[str] = None,
) -> CommandRequestObject:
    return CommandRequestObject(
        cid=cid or secrets.token_hex(16),
        command_type=CommandType.PaymentCommand,
        command=Command(
            _ObjectType=CommandType.PaymentCommand,
            payment=payment,
        ),
    )


def reply_request(
    cid: typing.Optional[str],
    err: typing.Union[None, OffChainErrorObject, typing.List[OffChainErrorObject]] = None,
) -> CommandResponseObject:
    if isinstance(err, list):
        errors = err
    elif isinstance(err, OffChainErrorObject):
        errors = [err]
    else:
        errors = None

    return CommandResponseObject(
        status=CommandResponseStatus.failure if errors else CommandResponseStatus.success,
        error=errors,
        cid=cid,
    )


def individual_kyc_data(**kwargs) -> KycDataObject:  # pyre-ignore
    return KycDataObject(
        type=KycDataObjectType.individual,
        **kwargs,
    )


def entity_kyc_data(**kwargs) -> KycDataObject:  # pyre-ignore
    return KycDataObject(
        type=KycDataObjectType.entity,
        **kwargs,
    )
