# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem.offchain import Status, Action
from .wallet import ActionResult
import pytest, typing


AMOUNT = 1_000_000_000
BOTH_READY = {"sender": Status.ready_for_settlement, "receiver": Status.ready_for_settlement}


@pytest.fixture()
def setup_env(wallet_apps):
    sender_wallet = wallet_apps["sender"]
    receiver_wallet = wallet_apps["receiver"]
    sender_vasp_balance = sender_wallet.vasp_balance()
    receiver_vasp_balance = receiver_wallet.vasp_balance()

    sender_wallet.add_user("foo")
    sender_wallet.add_user("user-x")
    sender_wallet.add_user("hello")

    receiver_wallet.add_user("bar")
    receiver_wallet.add_user("user-y")
    receiver_wallet.add_user("world")

    def assert_final_status(
        final_status: typing.Dict[str, Status],
        balance_change: typing.Optional[int] = 0,
    ) -> None:

        sender_data = sender_wallet.offchain_records
        receiver_data = receiver_wallet.offchain_records
        assert len(sender_data) == 1
        assert len(receiver_data) == 1

        ref_id = list(sender_data.keys())[0]
        sender_record = sender_data[ref_id]
        assert sender_record.cid == receiver_data[ref_id].cid
        assert sender_record.cmd_json == receiver_data[ref_id].cmd_json

        assert sender_record.payment_object().sender.status.status == final_status["sender"]
        assert sender_record.payment_object().receiver.status.status == final_status["receiver"]

        assert sender_wallet.vasp_balance() == sender_vasp_balance - balance_change
        assert receiver_wallet.vasp_balance() == receiver_vasp_balance + balance_change

        # nothing left
        assert sender_wallet.run_once_background_job() == None
        assert receiver_wallet.run_once_background_job() == None

    return (sender_wallet, receiver_wallet, assert_final_status)


def test_travel_rule_data_exchange_happy_path(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert receiver_app.run_once_background_job() == None
    assert sender_app.run_once_background_job() == (Action.SUBMIT_TXN, ActionResult.TXN_EXECUTED)
    assert receiver_app.run_once_background_job() == None

    assert_final_status(BOTH_READY, AMOUNT)


def test_travel_rule_data_exchange_receiver_reject_sender_kyc_data(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    receiver_app.evaluate_kyc_data_result = {"foo": ActionResult.REJECT}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.REJECT)

    assert_final_status({"sender": Status.needs_kyc_data, "receiver": Status.abort})


def test_travel_rule_data_exchange_receiver_soft_match_reject(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    receiver_app.evaluate_kyc_data_result = {"foo": ActionResult.SOFT_MATCH}
    receiver_app.manual_review_result = {"foo": ActionResult.REJECT}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert sender_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert receiver_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.REJECT)

    assert_final_status({"sender": Status.needs_kyc_data, "receiver": Status.abort})


def test_travel_rule_data_exchange_receiver_soft_match_pass(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    receiver_app.evaluate_kyc_data_result = {"foo": ActionResult.SOFT_MATCH}
    receiver_app.manual_review_result = {"foo": ActionResult.PASS}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert sender_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert receiver_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.PASS)
    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert receiver_app.run_once_background_job() == None

    assert sender_app.run_once_background_job() == (Action.SUBMIT_TXN, ActionResult.TXN_EXECUTED)
    assert receiver_app.run_once_background_job() == None

    assert_final_status(BOTH_READY, AMOUNT)


def test_travel_rule_data_exchange_sender_rejects_receiver_kyc_data(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    sender_app.evaluate_kyc_data_result = {"bar": ActionResult.REJECT}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.REJECT)
    assert receiver_app.run_once_background_job() == None

    assert_final_status({"sender": Status.abort, "receiver": Status.ready_for_settlement})


def test_travel_rule_data_exchange_sender_soft_match_reject(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    sender_app.evaluate_kyc_data_result = {"bar": ActionResult.SOFT_MATCH}
    sender_app.manual_review_result = {"bar": ActionResult.REJECT}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert receiver_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert sender_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.REJECT)
    assert receiver_app.run_once_background_job() == None

    assert_final_status({"sender": Status.abort, "receiver": Status.ready_for_settlement})


def test_travel_rule_data_exchange_sender_soft_match_pass(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    sender_app.evaluate_kyc_data_result = {"bar": ActionResult.SOFT_MATCH}
    sender_app.manual_review_result = {"bar": ActionResult.PASS}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert receiver_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert sender_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.PASS)
    assert receiver_app.run_once_background_job() == None
    assert sender_app.run_once_background_job() == (Action.SUBMIT_TXN, ActionResult.TXN_EXECUTED)
    assert receiver_app.run_once_background_job() == None

    assert_final_status(BOTH_READY, AMOUNT)


def test_travel_rule_data_exchange_receiver_soft_match_pass_sender_soft_match_reject(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    receiver_app.evaluate_kyc_data_result = {"foo": ActionResult.SOFT_MATCH}
    receiver_app.manual_review_result = {"foo": ActionResult.PASS}
    sender_app.evaluate_kyc_data_result = {"bar": ActionResult.SOFT_MATCH}
    sender_app.manual_review_result = {"bar": ActionResult.REJECT}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert sender_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert receiver_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.PASS)

    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert receiver_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert sender_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.REJECT)
    assert receiver_app.run_once_background_job() == None

    assert_final_status({"sender": Status.abort, "receiver": Status.ready_for_settlement})


def test_travel_rule_data_exchange_receiver_soft_match_pass_sender_soft_match_pass(setup_env):
    sender_app, receiver_app, assert_final_status = setup_env

    receiver_app.evaluate_kyc_data_result = {"foo": ActionResult.SOFT_MATCH}
    receiver_app.manual_review_result = {"foo": ActionResult.PASS}
    sender_app.evaluate_kyc_data_result = {"bar": ActionResult.SOFT_MATCH}
    sender_app.manual_review_result = {"bar": ActionResult.PASS}

    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)
    sender_app.pay("foo", intent_id)

    assert sender_app.run_once_background_job() == None
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert sender_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert receiver_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.PASS)

    assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.SOFT_MATCH)
    assert receiver_app.run_once_background_job() == (Action.CLEAR_SOFT_MATCH, ActionResult.SENT_ADDITIONAL_KYC_DATA)
    assert sender_app.run_once_background_job() == (Action.REVIEW_KYC_DATA, ActionResult.PASS)
    assert receiver_app.run_once_background_job() == None

    assert sender_app.run_once_background_job() == (Action.SUBMIT_TXN, ActionResult.TXN_EXECUTED)
    assert receiver_app.run_once_background_job() == None

    assert_final_status(BOTH_READY, AMOUNT)
