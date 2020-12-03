# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from .types import StatusObject, Status, PaymentActorObject, PaymentObject, KycDataObject
from .role import Role, Action
from .state import Machine, State, Value, build_machine, new_transition, require, field, value

import typing


def status(actor: str, s: Status) -> Value[PaymentObject, Status]:
    return value(f"{actor}.status.status", s)


S_INIT: State[PaymentObject] = State(
    id="S_INIT",
    require=require(
        status("sender", Status.needs_kyc_data),
        status("receiver", Status.none),
        field("sender.kyc_data"),
    ),
)
S_ABORT: State[PaymentObject] = State(
    id="S_ABORT",
    require=require(
        status("sender", Status.abort),
        status("receiver", Status.ready_for_settlement),
    ),
)
S_SOFT: State[PaymentObject] = State(
    id="S_SOFT",
    require=require(
        status("sender", Status.soft_match),
        status("receiver", Status.ready_for_settlement),
        field("receiver.kyc_data.additional_kyc_data", not_set=True),
    ),
)
S_SOFT_SEND: State[PaymentObject] = State(
    id="S_SOFT_SEND",
    require=require(
        status("sender", Status.needs_kyc_data),
        field("sender.kyc_data.additional_kyc_data"),
        status("receiver", Status.soft_match),
    ),
)

READY: State[PaymentObject] = State(
    id="READY",
    require=require(
        status("sender", Status.ready_for_settlement),
        status("receiver", Status.ready_for_settlement),
    ),
)
R_ABORT: State[PaymentObject] = State(
    id="R_ABORT",
    require=require(
        status("sender", Status.needs_kyc_data),
        status("receiver", Status.abort),
    ),
)
R_SOFT: State[PaymentObject] = State(
    id="R_SOFT",
    require=require(
        status("sender", Status.needs_kyc_data),
        field("sender.kyc_data.additional_kyc_data", not_set=True),
        status("receiver", Status.soft_match),
    ),
)
R_SOFT_SEND: State[PaymentObject] = State(
    id="R_SOFT_SEND",
    require=require(
        status("sender", Status.soft_match),
        status("receiver", Status.ready_for_settlement),
        field("receiver.kyc_data.additional_kyc_data"),
    ),
)
R_SEND: State[PaymentObject] = State(
    id="R_SEND",
    require=require(
        status("sender", Status.needs_kyc_data),
        status("receiver", Status.ready_for_settlement),
        field("receiver.kyc_data"),
        field("recipient_signature"),
    ),
)


MACHINE: Machine[PaymentObject] = build_machine(
    [
        new_transition(S_INIT, R_SEND),
        new_transition(S_INIT, R_ABORT),
        new_transition(S_INIT, R_SOFT),
        new_transition(R_SEND, READY),
        new_transition(R_SEND, S_ABORT),
        new_transition(R_SEND, S_SOFT),
        new_transition(R_SOFT, S_SOFT_SEND),
        new_transition(S_SOFT_SEND, R_ABORT),
        new_transition(S_SOFT_SEND, R_SEND),
        new_transition(S_SOFT, R_SOFT_SEND),
        new_transition(R_SOFT_SEND, S_ABORT),
        new_transition(R_SOFT_SEND, READY),
    ]
)


FOLLOW_UP: typing.Dict[State[PaymentObject], typing.Optional[typing.Tuple[Role, Action]]] = {
    S_INIT: (Role.RECEIVER, Action.EVALUATE_KYC_DATA),
    R_SEND: (Role.SENDER, Action.EVALUATE_KYC_DATA),
    R_ABORT: None,
    R_SOFT: (Role.SENDER, Action.CLEAR_SOFT_MATCH),
    READY: (Role.SENDER, Action.SUBMIT_TXN),
    S_ABORT: None,
    S_SOFT: (Role.RECEIVER, Action.CLEAR_SOFT_MATCH),
    S_SOFT_SEND: (Role.RECEIVER, Action.REVIEW_KYC_DATA),
    R_SOFT_SEND: (Role.SENDER, Action.REVIEW_KYC_DATA),
}


def trigger_role(state: State[PaymentObject]) -> Role:
    """The role triggers the action / event to produce the PaymentObject"""

    if state in [R_SEND, R_ABORT, R_SOFT, R_SOFT_SEND]:
        return Role.RECEIVER
    return Role.SENDER


def follow_up_action(role: Role, state: State[PaymentObject]) -> typing.Optional[Action]:
    followup = FOLLOW_UP[state]
    if not followup:
        return None
    follow_up_role, action = followup
    return action if follow_up_role == role else None


def summary(obj: typing.Union[PaymentObject, PaymentActorObject, StatusObject, KycDataObject, str, None]) -> str:
    if obj is None:
        return "-"
    if isinstance(obj, str):
        return "s"
    if isinstance(obj, KycDataObject):
        return "k+" if obj.additional_kyc_data else "k"
    if isinstance(obj, StatusObject):
        return obj.status
    if isinstance(obj, PaymentActorObject):
        return "_".join([summary(obj.status), summary(obj.kyc_data)])
    if isinstance(obj, PaymentObject):
        return "_".join([summary(obj.sender), summary(obj.receiver), summary(obj.recipient_signature)])
    return "?"
