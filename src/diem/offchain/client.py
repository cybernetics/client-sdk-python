# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

import requests, typing, dataclasses, uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from . import (
    Role,
    Command,
    CommandRequestObject,
    CommandResponseObject,
    CommandResponseStatus,
    PaymentObject,
    jws,
    invalid_request,
    http_header,
    validate,
)

from .. import jsonrpc, diem_types, identifier, utils


DEFAULT_CONNECT_TIMEOUT_SECS: float = 2.0
DEFAULT_TIMEOUT_SECS: float = 5.0


@dataclasses.dataclass(frozen=True)
class CommandResponseFailure(Exception):
    response: CommandResponseObject


@dataclasses.dataclass
class Client:
    my_parent_vasp_address: diem_types.AccountAddress
    jsonrpc_client: jsonrpc.Client
    hrp: str
    session: requests.Session = dataclasses.field(default_factory=lambda: requests.Session())
    timeout: typing.Tuple[float, float] = dataclasses.field(
        default_factory=lambda: (DEFAULT_CONNECT_TIMEOUT_SECS, DEFAULT_TIMEOUT_SECS)
    )
    my_parent_vasp_account_id: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.my_parent_vasp_account_id = self.account_id(self.my_parent_vasp_address)

    def send_request(
        self, role: Role, request: CommandRequestObject, sign: typing.Callable[[bytes], bytes]
    ) -> CommandResponseObject:
        payment = request.command.payment
        op_account_id = role.opposite().payment_actor(payment).address
        base_url, public_key = self.get_base_url_and_compliance_key(op_account_id)
        response = self.session.post(
            f"{base_url.rstrip('/')}/v1/command",
            data=jws.serialize(request, sign),
            headers={
                http_header.X_REQUEST_ID: uuid.uuid1().hex,
                http_header.X_VERIFICATION_KEY_ADDRESS: self.my_parent_vasp_account_id,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        resp_obj = jws.deserialize(response.content, CommandResponseObject, public_key.verify)

        if resp_obj.status == CommandResponseStatus.failure:
            raise CommandResponseFailure(response=resp_obj)

        return resp_obj

    def verify_request(self, jws_key_address: str, request_bytes: bytes) -> CommandRequestObject:
        _, public_key = self.get_base_url_and_compliance_key(jws_key_address)
        try:
            return jws.deserialize(request_bytes, CommandRequestObject, public_key.verify)
        except ValueError as e:
            raise invalid_request(f"deserialize CommandRequestObject JWS bytes failed: {e}") from e

    def validate_inbound_command(self, command: Command, prior: typing.Optional[Command]) -> Role:
        if command.payment:
            my_role = self.my_role(command.payment)
            validate.inbound_payment(command.payment, my_role.opposite(), prior.payment if prior else None)

        return my_role

    def my_role(self, obj: PaymentObject) -> Role:
        if self.is_my_account_id(obj.sender.address):
            return Role.SENDER
        if self.is_my_account_id(obj.receiver.address):
            return Role.RECEIVER

        raise invalid_request("unknown actor addresses: {obj}")

    def is_my_account_id(self, account_id: str) -> bool:
        account_address, _ = identifier.decode_account(account_id, self.hrp)
        if self.my_parent_vasp_account_id == self.account_id(account_address):
            return True
        account = self.jsonrpc_client.get_account(account_address)
        if account.role.parent_vasp_address:
            return self.my_parent_vasp_account_id == self.account_id(account.role.parent_vasp_address)
        return False

    def account_id(self, address: typing.Union[diem_types.AccountAddress, bytes, str]) -> str:
        return identifier.encode_account(utils.account_address(address), None, self.hrp)

    def get_base_url_and_compliance_key(self, account_id: str) -> typing.Tuple[str, Ed25519PublicKey]:
        account_address, _ = identifier.decode_account(account_id, self.hrp)
        return self.jsonrpc_client.get_base_url_and_compliance_key(account_address)
