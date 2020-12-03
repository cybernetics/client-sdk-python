# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

import typing, threading, dataclasses
from enum import Enum
from http import server
from diem import (
    identifier,
    jsonrpc,
    diem_types,
    stdlib,
    testnet,
    utils,
    LocalAccount,
    offchain,
)
import logging, queue

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class OffchainRecord:
    ref_id: str
    cid: str
    role: offchain.Role
    cmd_json: str

    def payment_object(self) -> offchain.PaymentObject:
        return self.command().payment

    def command(self) -> offchain.Command:
        return offchain.from_json(self.cmd_json, offchain.Command)

    def opposite_kyc_data(self) -> typing.Optional[offchain.KycDataObject]:
        return self.role.opposite().payment_actor(self.payment_object()).kyc_data


@dataclasses.dataclass(frozen=True)
class User:
    name: str
    subaddresses: typing.List[str] = dataclasses.field(default_factory=lambda: [])

    def kyc_data(self) -> offchain.KycDataObject:
        return offchain.individual_kyc_data(
            given_name=self.name,
            surname=f"surname-{self.name}",
            address=offchain.AddressObject(city="San Francisco"),
        )

    def additional_kyc_data(self) -> str:
        return f"{self.name}'s secret"


class ActionResult(Enum):
    PASS = "pass"
    REJECT = "reject"
    SOFT_MATCH = "soft_match"
    SENT_ADDITIONAL_KYC_DATA = "sent_additional_kyc_data"
    TXN_EXECUTED = "transaction_executed"
    SEND_REQUEST_FAILED = "send_request_failed"
    SEND_REQUEST_SUCCESS = "send_request_success"


@dataclasses.dataclass
class WalletApp:
    """WalletApp is an example of custodial wallet application"""

    @staticmethod
    def generate(name: str) -> "WalletApp":
        """generate a WalletApp running on testnet"""

        offchain_service_port = offchain.http_server.get_available_port()
        account = testnet.gen_vasp_account(f"http://localhost:{offchain_service_port}")
        w = WalletApp(name=name, parent_vasp=account, offchain_service_port=offchain_service_port)
        w.add_child_vasp()
        return w

    name: str
    parent_vasp: LocalAccount
    offchain_service_port: int

    hrp: str = dataclasses.field(default=identifier.TLB)
    jsonrpc_client: jsonrpc.Client = dataclasses.field(default_factory=lambda: testnet.create_client())
    offchain_records: typing.Dict[str, OffchainRecord] = dataclasses.field(default_factory=lambda: {})
    child_vasps: typing.List[LocalAccount] = dataclasses.field(default_factory=lambda: [])
    users: typing.Dict[str, User] = dataclasses.field(default_factory=lambda: {})
    evaluate_kyc_data_result: typing.Dict[str, ActionResult] = dataclasses.field(default_factory=lambda: {})
    manual_review_result: typing.Dict[str, ActionResult] = dataclasses.field(default_factory=lambda: {})
    background_tasks: queue.Queue = dataclasses.field(default_factory=lambda: queue.Queue())

    def __post_init__(self) -> None:
        self.compliance_key = self.parent_vasp.compliance_key
        self.offchain_client = offchain.Client(self.parent_vasp.account_address, self.jsonrpc_client, self.hrp)

    # --------------------- end user interaction --------------------------

    def pay(self, user_name: str, intent_id: str) -> str:
        """make payment from given user account to intent_id

        returns payment reference id"""

        intent = identifier.decode_intent(intent_id, self.hrp)
        req = offchain.init_payment_request(
            self._gen_user_account_id(user_name),
            self.users[user_name].kyc_data(),
            intent.account_id,
            intent.amount,
            intent.currency_code,
        )
        my_role = offchain.Role.SENDER

        self._save_offchain_record(req, my_role)
        self._send_request(req, my_role)
        return req.command.payment.reference_id

    def gen_intent_id(
        self, user_name: int, amount: int, currency: typing.Optional[str] = testnet.TEST_CURRENCY_CODE
    ) -> str:
        account_id = self._gen_user_account_id(user_name)
        return identifier.encode_intent(account_id, currency, amount)

    # --------------------- offchain integration --------------------------

    def process_inbound_request(
        self, x_request_id: str, jws_key_address: str, request_bytes: bytes
    ) -> typing.Tuple[int, bytes]:
        request = None
        try:
            request = self.offchain_client.verify_request(jws_key_address, request_bytes)
            ref_id = request.command.payment.reference_id
            record = self._find_offchain_record_for_update(ref_id)
            command = record.command() if record else None
            # 1. process the request if it is not same with existing command.
            if request.command != command:
                # 2. validate new request command
                my_role = self.offchain_client.validate_inbound_command(request.command, command)
                # 3. save if validation passed
                self._save_offchain_record(request, my_role)

            resp = offchain.reply_request(request.cid)
            code = 200
        except offchain.Error as e:
            logger.exception(e)
            resp = offchain.reply_request(request.cid if request else None, e.obj)
            code = 400

        return (code, offchain.jws.serialize(resp, self.compliance_key.sign))

    def run_once_background_job(self) -> typing.Union[ActionResult, typing.Tuple[offchain.Action, ActionResult]]:
        try:
            task = self.background_tasks.get_nowait()
            return task(self)
        except queue.Empty:
            return None

    # --------------------- admin --------------------------

    def start_server(self) -> server.HTTPServer:
        return offchain.http_server.start_local(self.offchain_service_port, self.process_inbound_request)

    def add_child_vasp(self) -> jsonrpc.Transaction:
        self.child_vasps.append(testnet.gen_child_vasp(self.parent_vasp))

    def add_user(self, name) -> None:
        self.users[name] = User(name)

    def vasp_balance(self, currency: str = testnet.TEST_CURRENCY_CODE) -> int:
        balance = 0
        for vasp in [self.parent_vasp] + self.child_vasps:
            balance += utils.balance(self.jsonrpc_client.get_account(vasp.account_address), currency)
        return balance

    def clear_data(self) -> None:
        self.evaluate_kyc_data_result = {}
        self.manual_review_result = {}
        self.users = {}
        self.offchain_records = {}
        self.background_tasks = queue.Queue()

    # -------- offchain business actions ---------------

    def _send_additional_kyc_data(self, record: OffchainRecord) -> None:
        account_id = record.role.payment_actor(record.payment_object()).address
        _, subaddress = identifier.decode_account(account_id, self.hrp)
        user = self._find_user_by_subaddress(subaddress)
        self._update_payment_record(record, additional_kyc_data=user.additional_kyc_data())
        return ActionResult.SENT_ADDITIONAL_KYC_DATA

    def _submit_travel_rule_txn(
        self,
        record: OffchainRecord,
    ) -> ActionResult:
        payment = record.payment_object()
        account_address, subaddress = identifier.decode_account(payment.sender.address, self.hrp)
        receiver_address, _ = identifier.decode_account(payment.receiver.address, self.hrp)
        metadata, _ = offchain.travel_rule_metadata(payment, self.hrp)

        child_vasp = self._find_child_vasp(account_address)
        testnet.exec_txn(
            child_vasp,
            stdlib.encode_peer_to_peer_with_metadata_script(
                currency=utils.currency_code(payment.action.currency),
                payee=receiver_address,
                amount=payment.action.amount,
                metadata=metadata,
                metadata_signature=bytes.fromhex(payment.recipient_signature),
            ),
        )

        return ActionResult.TXN_EXECUTED

    def _evaluate_kyc_data(self, record: OffchainRecord) -> ActionResult:
        ret = self.evaluate_kyc_data_result.get(record.opposite_kyc_data().given_name, ActionResult.PASS)

        if ret == ActionResult.SOFT_MATCH:
            self._update_payment_record(record, status=offchain.Status.soft_match)
        else:
            self._kyc_data_result("evaluate key data", ret, record)
        return ret

    def _manual_review(self, record: OffchainRecord) -> ActionResult:
        ret = self.manual_review_result.get(record.opposite_kyc_data().given_name, ActionResult.PASS)
        self._kyc_data_result("review", ret, record)
        return ret

    def _kyc_data_result(self, action: str, ret: ActionResult, record: OffchainRecord):
        if ret == ActionResult.PASS:
            if record.role == offchain.Role.RECEIVER:
                self._send_kyc_data_and_receipient_signature(record)
            else:
                self._update_payment_record(record, status=offchain.Status.ready_for_settlement)
        else:
            self._abort(record, offchain.OffChainErrorAbortCode.reject_kyc_data, f"{action}: {ret}")

    def _send_kyc_data_and_receipient_signature(
        self,
        record: OffchainRecord,
    ) -> None:
        payment = record.payment_object()
        _, sig_msg = offchain.travel_rule_metadata(payment, self.hrp)
        _, subaddress = identifier.decode_account(payment.receiver.address, self.hrp)

        user = self._find_user_by_subaddress(subaddress)

        self._update_payment_record(
            record,
            recipient_signature=self.compliance_key.sign(sig_msg).hex(),
            kyc_data=user.kyc_data(),
            status=offchain.Status.ready_for_settlement,
        )

    # ---------------------- offchain utils ---------------------------

    def _abort(self, record: OffchainRecord, code: str, msg: str) -> None:
        self._update_payment_record(record, status=offchain.Status.abort, abort_code=code, abort_message=msg)

    def _update_payment_record(self, record: OffchainRecord, **changes) -> None:
        request = offchain.update_payment_request(record.role, record.payment_object(), **changes)
        self._save_offchain_record(request, record.role)
        self._send_request(request, record.role)

    def _send_request(self, request: offchain.CommandRequestObject, my_role: offchain.Role) -> ActionResult:
        try:
            self.offchain_client.send_request(my_role, request, self.compliance_key.sign)
            return ActionResult.SEND_REQUEST_SUCCESS
        except Exception as e:
            # log error, and retry by background task
            logger.exception(e)
            self.background_tasks.put(lambda app: app._send_request(request, my_role))
            return ActionResult.SEND_REQUEST_FAILED

    def _save_offchain_record(self, request: offchain.CommandRequestObject, my_role: offchain.Role) -> None:
        ref_id = request.command.payment.reference_id
        self.offchain_records[ref_id] = OffchainRecord(
            ref_id=ref_id,
            cid=request.cid,
            role=my_role,
            cmd_json=offchain.to_json(request.command),
        )
        # when process inbound request or sender sets ready_for_settlement status
        # we have follow up action
        action = offchain.follow_up_action(my_role, request.command.payment)
        if action:
            self.background_tasks.put(lambda app: app._offchain_business_action(action, ref_id))

    def _offchain_business_action(
        self, action: offchain.Action, ref_id: str
    ) -> typing.Union[ActionResult, typing.Tuple[offchain.Action, ActionResult]]:
        record = self._find_offchain_record_for_update(ref_id)
        actions = {
            offchain.Action.EVALUATE_KYC_DATA: self._evaluate_kyc_data,
            offchain.Action.SUBMIT_TXN: self._submit_travel_rule_txn,
            offchain.Action.CLEAR_SOFT_MATCH: self._send_additional_kyc_data,
            offchain.Action.REVIEW_KYC_DATA: self._manual_review,
        }
        ret = actions[action](record)
        # return action and action result for test
        return (action, ret)

    def _find_offchain_record_for_update(self, ref_id: str) -> typing.Optional[OffchainRecord]:
        """production implementation should find and lock the record to avoid concurrent updates"""

        return self.offchain_records.get(ref_id)

    # ---------------------- users ---------------------------

    def _find_user_by_subaddress(self, subaddress: bytes) -> User:
        for u in self.users.values():
            if subaddress in u.subaddresses:
                return u
        raise ValueError(f"could not find user by subaddress: {subaddress.hex()}, {self.name}")

    def _gen_user_account_id(self, user_name: int) -> str:
        subaddress = identifier.gen_subaddress()
        self.users[user_name].subaddresses.append(subaddress)
        return identifier.encode_account(self._available_child_vasp().account_address, subaddress, self.hrp)

    # ---------------------- child vasps ---------------------------

    def _available_child_vasp(self) -> LocalAccount:
        return self.child_vasps[0]

    def _find_child_vasp(self, address: diem_types.AccountAddress) -> LocalAccount:
        for vasp in self.child_vasps:
            if vasp.account_address == address:
                return vasp

        raise ValueError(f"could not find child vasp by address: {address.to_hex()}")
