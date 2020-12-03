# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

""" This package provides data structures and utilities for implementing Offchain API Service.

See [Diem Offchain API](https://dip.diem.com/dip-1/) for more details.

"""

from .types import (
    OffChainErrorType,
    OffChainErrorObject,
)

import typing


class Error(Exception):
    obj: OffChainErrorObject

    def __init__(self, obj: OffChainErrorObject) -> None:
        super(Exception, self).__init__(obj)
        self.obj = obj


def invalid_request(msg: str) -> Error:
    return command_error("invalid-request", message=msg)


def command_error(code: str, field: typing.Optional[str] = None, message: typing.Optional[str] = None) -> Error:
    return Error(obj=OffChainErrorObject(type=OffChainErrorType.command_error, code=code, field=field, message=message))


def protocol_error(code: str, field: typing.Optional[str] = None, message: typing.Optional[str] = None) -> Error:
    return Error(
        obj=OffChainErrorObject(type=OffChainErrorType.protocol_error, code=code, field=field, message=message)
    )
