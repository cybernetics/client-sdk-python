# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

from . import WalletApp
import pytest, typing


def launch_wallet_app(name: str) -> WalletApp:
    app = WalletApp.generate(f"{name}'s wallet app")
    app.start_server()
    return app


@pytest.fixture(scope="module")
def wallet_apps() -> typing.List[WalletApp]:
    return {name: launch_wallet_app(name) for name in ["sender", "receiver"]}


@pytest.fixture(autouse=True)
def teardown_wallet_apps(wallet_apps):
    yield

    for app in wallet_apps.values():
        app.clear_data()
