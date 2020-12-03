# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from enum import Enum
from . import PaymentObject, PaymentActorObject

import dataclasses, typing


class Action(Enum):
    EVALUATE_KYC_DATA = "evaluate_kyc_data"
    REVIEW_KYC_DATA = "review_kyc_data"
    CLEAR_SOFT_MATCH = "clear_soft_match"
    SUBMIT_TXN = "submit_transaction"


class Role(Enum):
    SENDER = "sender"
    RECEIVER = "receiver"

    def opposite(self) -> "Role":
        if self == Role.SENDER:
            return Role.RECEIVER
        else:
            return Role.SENDER

    def payment_actor(self, payment: PaymentObject) -> PaymentActorObject:
        if self == Role.SENDER:
            return payment.sender
        else:
            return payment.receiver
