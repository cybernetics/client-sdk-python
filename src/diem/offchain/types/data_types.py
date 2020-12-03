# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field as datafield

import time, typing


class KycDataObjectType:
    individual = "individual"
    entity = "entity"


class CommandType:
    PaymentCommand = "PaymentCommand"
    FundPullPreApprovalCommand = "FundPullPreApprovalCommand"


class CommandResponseStatus:
    success = "success"
    failure = "failure"


class OffChainErrorType:
    """command_error occurs in response to a Command failing to be applied - for example, invalid _reads values,
    or high level validation errors.
    protocol_error occurs in response to a failure related to the lower-level protocol.
    """

    command_error = "command_error"
    protocol_error = "protocol_error"


class OffChainErrorAbortCode:
    reject_kyc_data = "rejected"
    no_kyc_needed = "no-kyc-needed"


class Status:
    # No status is yet set from this actor.
    none = "none"
    # KYC data about the subaddresses is required by this actor.
    needs_kyc_data = "needs_kyc_data"
    # Transaction is ready for settlement according to this actor
    ready_for_settlement = "ready_for_settlement"
    # Indicates the actor wishes to abort this payment, instead of settling it.
    abort = "abort"
    # KYC data resulted in a soft-match, request additional_kyc_data.
    soft_match = "soft_match"


@dataclass(frozen=True)
class StatusObject:
    # Status of the payment from the perspective of this actor. Required
    status: str
    # In the case of an abort status, this field may be used to describe the reason for the abort.
    abort_code: typing.Optional[str] = datafield(default=None)
    # Additional details about this error. To be used only when code is populated
    abort_message: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class NationalIdObject:
    # Indicates the national ID value - for example, a social security number
    id_value: typing.Optional[str] = datafield(default=None)
    # Two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
    country: typing.Optional[str] = datafield(default=None)
    # Indicates the type of the ID
    type: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class AddressObject:
    # The city, district, suburb, town, or village
    city: typing.Optional[str] = datafield(default=None)
    # Two-letter country code (https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
    country: typing.Optional[str] = datafield(default=None)
    # Address line 1
    line1: typing.Optional[str] = datafield(default=None)
    # Address line 2 - apartment, unit, etc.
    line2: typing.Optional[str] = datafield(default=None)
    # ZIP or postal code
    postal_code: typing.Optional[str] = datafield(default=None)
    # State, county, province, region.
    state: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class KycDataObject:
    # Must be either “individual” or “entity”. Required.
    type: str
    # Used to help determine what type of data this will deserialize into. Always set to KYC_DATA.
    payload_type: str = datafield(default="KYC_DATA")
    # Version identifier to allow modifications to KYC data Object without needing to bump version of entire API set. Set to 1
    payload_version: int = datafield(default=1)
    # Legal given name of the user for which this KYC data Object applies.
    given_name: typing.Optional[str] = datafield(default=None)
    # Legal surname of the user for which this KYC data Object applies.
    surname: typing.Optional[str] = datafield(default=None)
    # Physical address data for this account
    address: typing.Optional[AddressObject] = datafield(default=None)
    # Date of birth for the holder of this account. Specified as an ISO 8601 calendar date format: https:#en.wikipedia.org/wiki/ISO_8601
    dob: typing.Optional[str] = datafield(default=None)
    # Place of birth for this user. line1 and line2 fields should not be populated for this usage of the address Object
    place_of_birth: typing.Optional[AddressObject] = datafield(default=None)
    # National ID information for the holder of this account
    national_id: typing.Optional[NationalIdObject] = datafield(default=None)
    # Name of the legal entity. Used when subaddress represents a legal entity rather than an individual. KycDataObject should only include one of legal_entity_name OR given_name/surname
    legal_entity_name: typing.Optional[str] = datafield(default=None)
    # Freeform KYC data. If a soft-match occurs, this field should be used to specify additional KYC data which can be used to clear the soft-match. It is suggested that this data be JSON, XML, or another human-readable form.
    additional_kyc_data: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class PaymentActionObject:
    amount: int
    currency: str
    action: str = datafield(default="charge")
    # Unix timestamp (seconds) indicating the time that the payment Command was created.
    timestamp: int = datafield(default_factory=lambda: int(time.time()))


@dataclass(frozen=True)
class PaymentActorObject:
    address: str
    status: StatusObject
    kyc_data: typing.Optional[KycDataObject] = datafield(default=None)
    metadata: typing.Optional[typing.List[str]] = datafield(default=None)


@dataclass(frozen=True)
class PaymentObject:
    reference_id: str
    sender: PaymentActorObject
    receiver: PaymentActorObject
    action: PaymentActionObject
    original_payment_reference_id: typing.Optional[str] = datafield(default=None)
    recipient_signature: typing.Optional[str] = datafield(default=None)
    description: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class Command:
    _ObjectType: str
    # PaymentObject that either creates a new payment or updates an existing payment.
    # An invalid update or initial payment Object results in a Command error.
    payment: typing.Optional[PaymentObject] = datafield(default=None)


@dataclass(frozen=True)
class CommandRequestObject:
    # A unique identifier for the Command.
    cid: str
    # A string representing the type of Command contained in the request.
    command_type: str
    command: Command
    _ObjectType: str = datafield(default="CommandRequestObject")


@dataclass(frozen=True)
class OffChainErrorObject:
    # Either "command_error" or "protocol_error".
    type: str
    # The error code of the corresponding error
    code: str
    # The field on which this error occurred
    field: typing.Optional[str] = datafield(default=None)
    # Additional details about this error
    message: typing.Optional[str] = datafield(default=None)


@dataclass(frozen=True)
class CommandResponseObject:
    # Either success or failure.
    status: str
    # The fixed string CommandResponseObject.
    _ObjectType: str = datafield(default="CommandResponseObject")
    # Details on errors when status == "failure"
    error: typing.Optional[typing.List[OffChainErrorObject]] = datafield(default=None)
    # The Command identifier to which this is a response.
    cid: typing.Optional[str] = datafield(default=None)
