# Copyright (c) The Diem Core Contributors
# SPDX-License-Identifier: Apache-2.0

import os
from setuptools import setup

this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="diem",
    version="0.6.2020120202", # bump up version for release, format 0.X.YYYYMMDDNN
    description="The Python Client SDK for Diem",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license="Apache-2.0",
    url="https://github.com/libra/client-sdk-python",
    # author="Diem Open Source",
    python_requires=">=3.7", # requires dataclasses
    packages=["diem"],
    # package_data={"": ["src/diem/jsonrpc/*.pyi"]},
    package_dir={"": "src"},
    include_package_data=True,  # see MANIFEST.in
    zip_safe=True,
    install_requires=["requests>=2.20.0", "cryptography>=2.8", "numpy>=1.18", "protobuf>=3.12.4", "marshmallow>=3.5.1"],
    setup_requires=[
        # Setuptools 18.0 properly handles Cython extensions.
        "setuptools>=18.0",
    ]
)
