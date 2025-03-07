# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import pytest

pytest_plugins = "tests_common.pytest_plugin"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    deprecations_ignore_path = pathlib.Path(__file__).parent.joinpath("deprecations_ignore.yml")
    dep_path = [deprecations_ignore_path] if deprecations_ignore_path.exists() else []
    config.inicfg["airflow_deprecations_ignore"] = (
        config.inicfg.get("airflow_deprecations_ignore", []) + dep_path  # type: ignore[assignment,operator]
    )


import json
import pathlib
import random
import re
import string
from inspect import currentframe
from json import JSONDecodeError
from os.path import dirname, join
from typing import Any, TypeVar
from unittest.mock import MagicMock

from httpx import Headers, Response
from msgraph_core import APIVersion


@pytest.fixture
def create_mock_connection(monkeypatch):
    """Helper fixture for create test connection."""
    from airflow.models import Connection

    T = TypeVar("T", dict, str, Connection)

    def wrapper(conn: T, conn_id: str | None = None):
        conn_id = conn_id or "test_conn_" + "".join(
            random.choices(string.ascii_lowercase + string.digits, k=6)
        )
        if isinstance(conn, dict):
            conn = Connection.from_json(conn)
        elif isinstance(conn, str):
            conn = Connection(uri=conn)

        if not isinstance(conn, Connection):
            raise TypeError(
                f"Fixture expected either JSON, URI or Connection type, but got {type(conn).__name__}"
            )
        if not conn.conn_id:
            conn.conn_id = conn_id

        monkeypatch.setenv(f"AIRFLOW_CONN_{conn.conn_id.upper()}", conn.get_uri())
        return conn

    return wrapper


@pytest.fixture
def create_mock_connections(create_mock_connection):
    """Helper fixture for create multiple test connections."""
    from airflow.models import Connection

    T = TypeVar("T", dict, str, Connection)

    def wrapper(*conns: T):
        return list(map(create_mock_connection, conns))

    return wrapper


@pytest.fixture
def mocked_connection(request, create_mock_connection):
    """Helper indirect fixture for create test connection."""
    return create_mock_connection(request.param)


def mock_connection(schema: str | None = None, host: str | None = None):
    from airflow.models import Connection

    connection = MagicMock(spec=Connection)
    connection.schema = schema
    connection.host = host
    return connection


def mock_json_response(status_code, *contents) -> Response:
    response = MagicMock(spec=Response)
    response.status_code = status_code
    response.headers = Headers({})
    response.content = b""
    if contents:
        response.json.side_effect = list(contents)
    else:
        response.json.return_value = None
    return response


def mock_response(status_code, content: Any = None, headers: dict | None = None) -> Response:
    response = MagicMock(spec=Response)
    response.status_code = status_code
    response.headers = Headers(headers or {})
    response.content = content
    response.json.side_effect = JSONDecodeError("", "", 0)
    return response


def remove_license_header(content: str) -> str:
    """
    Removes license header from the given content.
    """
    # Define the pattern to match both block and single-line comments
    pattern = r"(/\*.*?\*/)|(--.*?(\r?\n|\r))|(#.*?(\r?\n|\r))"

    # Check if there is a license header at the beginning of the file
    if re.match(pattern, content, flags=re.DOTALL):
        # Use re.DOTALL to allow .* to match newline characters in block comments
        return re.sub(pattern, "", content, flags=re.DOTALL).strip()
    return content.strip()


def load_json(*args: str):
    directory = currentframe().f_back.f_globals["__name__"].split(".")[:-2]  # type: ignore
    with open(join(dirname(__file__), join(*directory), join(*args)), encoding="utf-8") as file:
        return json.load(file)


def load_file(*args: str, mode="r", encoding="utf-8"):
    directory = currentframe().f_back.f_globals["__name__"].split(".")[:-2]  # type: ignore
    with open(join(dirname(__file__), join(*directory), join(*args)), mode=mode, encoding=encoding) as file:
        if mode == "r":
            return remove_license_header(file.read())
        return file.read()


def get_airflow_connection(
    conn_id: str,
    host: str = "graph.microsoft.com",
    login: str = "client_id",
    password: str = "client_secret",
    tenant_id: str = "tenant-id",
    azure_tenant_id: str | None = None,
    proxies: dict | None = None,
    scopes: list[str] | None = None,
    api_version: APIVersion | str | None = APIVersion.v1.value,
    authority: str | None = None,
    disable_instance_discovery: bool = False,
):
    from airflow.models import Connection

    extra = {
        "api_version": api_version,
        "proxies": proxies or {},
        "verify": False,
        "scopes": scopes or [],
        "authority": authority,
        "disable_instance_discovery": disable_instance_discovery,
    }

    if azure_tenant_id:
        extra["tenantId"] = azure_tenant_id
    else:
        extra["tenant_id"] = tenant_id

    return Connection(
        schema="https",
        conn_id=conn_id,
        conn_type="http",
        host=host,
        port=80,
        login=login,
        password=password,
        extra=extra,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    from airflow.providers.microsoft.azure.hooks.msgraph import KiotaRequestAdapterHook

    KiotaRequestAdapterHook.cached_request_adapters.clear()


@pytest.fixture
def powerbi_hook():
    from airflow.providers.microsoft.azure.hooks.powerbi import PowerBIHook

    return PowerBIHook(**{"conn_id": "powerbi_conn_id", "timeout": 3, "api_version": "v1.0"})
