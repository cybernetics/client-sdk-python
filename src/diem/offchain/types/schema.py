# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0


from marshmallow import Schema, fields, validate, post_load, post_dump
from . import data_types

import typing


T = typing.TypeVar("T")


class BaseSchema(Schema):
    @post_dump
    def remove_none_values(self, data, **kwargs):
        return {key: value for key, value in data.items() if value is not None}

    @post_load
    def make_obj(self, data, **kwargs) -> T:
        data_class = getattr(data_types, type(self).__name__)
        return data_class(**data)


class NationalIdObject(BaseSchema):
    id_value = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True)
    type = fields.Str(allow_none=True)


class AddressObject(BaseSchema):
    city = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True)
    line1 = fields.Str(allow_none=True)
    line2 = fields.Str(allow_none=True)
    postal_code = fields.Str(allow_none=True)
    state = fields.Str(allow_none=True)


class KycDataObject(BaseSchema):
    type = fields.Str(required=True, validate=validate.OneOf(["individual", "entity"]))
    payload_type = fields.Str(required=True, validate=validate.Equal("KYC_DATA"))
    payload_version = fields.Int(required=True, validate=validate.Equal(1))
    given_name = fields.Str(allow_none=True)
    surname = fields.Str(allow_none=True)
    address = fields.Nested(AddressObject, allow_none=True)
    dob = fields.Str(allow_none=True)
    place_of_birth = fields.Nested(AddressObject, allow_none=True)
    national_id = fields.Nested(NationalIdObject, allow_none=True)
    legal_entity_name = fields.Str(allow_none=True)
    additional_kyc_data = fields.Str(allow_none=True)


class StatusObject(BaseSchema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(
            [
                "none",
                "needs_kyc_data",
                "ready_for_settlement",
                "abort",
                "soft_match",
            ]
        ),
    )
    abort_code = fields.Str(allow_none=True)
    abort_message = fields.Str(allow_none=True)


class PaymentActionObject(BaseSchema):
    amount = fields.Int(required=True)
    currency = fields.Str(required=True)
    action = fields.Str(required=True, validate=validate.Equal("charge"))
    timestamp = fields.Int(required=True)


class PaymentActorObject(BaseSchema):
    address = fields.Str(required=True)
    status = fields.Nested(StatusObject, required=True)
    kyc_data = fields.Nested(KycDataObject, allow_none=True)
    metadata = fields.List(fields.Str(), allow_none=True)


class PaymentObject(BaseSchema):
    reference_id = fields.Str(required=True)
    sender = fields.Nested(PaymentActorObject, required=True)
    receiver = fields.Nested(PaymentActorObject, required=True)
    action = fields.Nested(PaymentActionObject, required=True)
    original_payment_reference_id = fields.Str(allow_none=True)
    recipient_signature = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)


class Command(BaseSchema):
    _ObjectType = fields.String(required=True, validate=validate.OneOf(["PaymentCommand"]))
    payment = fields.Nested(PaymentObject, allow_none=True)


class OffChainErrorObject(BaseSchema):
    type = fields.Str(required=True, validate=validate.OneOf(["command_error", "protocol_error"]))
    code = fields.Str(required=True)
    field = fields.Str(allow_none=True)
    message = fields.Str(allow_none=True)


class CommandRequestObject(BaseSchema):
    _ObjectType = fields.Str(required=True)
    cid = fields.Str(required=True)
    command_type = fields.Str(required=True, validate=validate.OneOf(["PaymentCommand"]))
    command = fields.Nested(Command, required=True)


class CommandResponseObject(BaseSchema):
    _ObjectType = fields.Str(required=True)
    status = fields.Str(required=True, validate=validate.OneOf(["success", "failure"]))
    error = fields.List(fields.Nested(OffChainErrorObject), allow_none=True)
    cid = fields.Str(allow_none=True)
