# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from diem.offchain import Status, Action, jws, http_header, CommandResponseObject
from diem import LocalAccount
from .wallet import ActionResult
import pytest, requests


AMOUNT = 1_000_000_000


@pytest.fixture()
def setup_env(wallet_apps):
    sender_wallet = wallet_apps["sender"]
    receiver_wallet = wallet_apps["receiver"]

    sender_wallet.add_user("foo")
    sender_wallet.add_user("user-x")
    sender_wallet.add_user("hello")

    receiver_wallet.add_user("bar")
    receiver_wallet.add_user("user-y")
    receiver_wallet.add_user("world")

    return (sender_wallet, receiver_wallet)


def test_send_initial_command_failed_by_command_response_error_and_retry_by_bg_job(monkeypatch, setup_env):
    sender_app, receiver_app = setup_env
    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)

    with monkeypatch.context() as m:
        m.setattr(sender_app, "compliance_key", LocalAccount.generate().compliance_key)
        sender_app.pay("foo", intent_id)

        assert len(sender_app.offchain_records) == 1
        assert len(receiver_app.offchain_records) == 0

        # retry error
        assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_FAILED
        assert len(sender_app.offchain_records) == 1
        assert len(receiver_app.offchain_records) == 0

    assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_SUCCESS

    assert len(sender_app.offchain_records) == 1
    assert len(receiver_app.offchain_records) == 1

    # receiver_app continues the flow after error is recovered
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)


def test_send_command_failed_by_http_error_and_retry_by_bg_job(monkeypatch, setup_env):
    sender_app, receiver_app = setup_env
    intent_id = receiver_app.gen_intent_id("bar", AMOUNT)

    with monkeypatch.context() as m:
        # receiver side save request failed, which causes 500 error to sender client
        m.setattr(receiver_app, "_save_offchain_record", raise_error(Exception(f"server internal error")))
        reference_id = sender_app.pay("foo", intent_id)

        assert len(sender_app.offchain_records) == 1
        assert len(receiver_app.offchain_records) == 0

        # retry error
        assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_FAILED
        assert len(sender_app.offchain_records) == 1
        assert len(receiver_app.offchain_records) == 0

    assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_SUCCESS

    assert len(sender_app.offchain_records) == 1
    assert len(receiver_app.offchain_records) == 1

    # receiver continues the flow after error is recovered
    assert receiver_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)

    with monkeypatch.context() as m:
        # receiver side save request failed, which causes 500 error to sender client
        m.setattr(receiver_app, "_save_offchain_record", raise_error(Exception(f"server internal error")))

        # action success but send request should fail
        assert sender_app.run_once_background_job() == (Action.EVALUATE_KYC_DATA, ActionResult.PASS)
        assert sender_status(sender_app, reference_id) == Status.ready_for_settlement
        assert sender_status(receiver_app, reference_id) == Status.needs_kyc_data

        # submit txn success, although send update req failed
        # todo: should we not submit txn until send update req success?
        assert sender_app.run_once_background_job() == (Action.SUBMIT_TXN, ActionResult.TXN_EXECUTED)
        # retry failed again
        assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_FAILED
        assert sender_status(sender_app, reference_id) == Status.ready_for_settlement
        assert sender_status(receiver_app, reference_id) == Status.needs_kyc_data

    assert sender_app.run_once_background_job() == ActionResult.SEND_REQUEST_SUCCESS
    assert sender_status(sender_app, reference_id) == Status.ready_for_settlement
    assert sender_status(receiver_app, reference_id) == Status.ready_for_settlement


def test_invalid_command_request_json(setup_env):
    sender_app, receiver_app = setup_env
    session = requests.Session()
    resp = session.post(
        f"http://localhost:{receiver_app.offchain_service_port}/v1/command",
        data=jws.serialize_string('"invalid_request_json"', sender_app.compliance_key.sign),
        headers={
            http_header.X_REQUEST_ID: "uuid",
            http_header.X_VERIFICATION_KEY_ADDRESS: sender_app.offchain_client.my_parent_vasp_account_id,
        },
    )
    assert resp.status_code == 400
    resp = jws.deserialize(resp.content, CommandResponseObject, receiver_app.compliance_key.public_key().verify)
    assert resp.cid is None
    assert resp.status == "failure"
    assert resp.error
    assert len(resp.error) == 1


def sender_status(wallet, ref_id):
    record = wallet.offchain_records[ref_id]
    return record.payment_object().sender.status.status


def raise_error(e: Exception):
    def fn(*args, **wargs):
        raise e

    return fn
