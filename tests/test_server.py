"""Protocol-level tests: drive CtxKitServer exactly the way an MCP client
does, plus a real end-to-end subprocess test over stdio."""
import json
import subprocess
import sys
import os
from pathlib import Path

import pytest

from meshctx_ctxkit.server import CtxKitServer, main as server_main

SRC = str(Path(__file__).resolve().parents[1] / "src")


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("CTXKIT_HOME", str(tmp_path / "home"))
    return CtxKitServer()


def _rpc(srv, method, params=None, mid=1):
    return srv.handle({"jsonrpc": "2.0", "id": mid, "method": method,
                       "params": params or {}})


def _text(resp):
    return json.loads(resp["result"]["content"][0]["text"])


class TestProtocol:
    def test_initialize(self, srv):
        resp = _rpc(srv, "initialize", {"protocolVersion": "2024-11-05"})
        assert resp["result"]["serverInfo"]["name"] == "ctxkit"

    def test_notification_gets_no_response(self, srv):
        assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    def test_tools_list_has_seven_tools(self, srv):
        resp = _rpc(srv, "tools/list")
        names = [t["name"] for t in resp["result"]["tools"]]
        assert names == ["ctx_remember", "ctx_recall", "ctx_forget",
                         "ctx_stats", "ctx_verify_text", "ctx_consensus",
                         "ctx_license"]

    def test_remember_recall_roundtrip(self, srv):
        out = _text(_rpc(srv, "tools/call",
                         {"name": "ctx_remember",
                          "arguments": {"text": "stripe key rotated on 3 May", "tags": ["ops"]}}))
        assert out["ok"] is True
        out = _text(_rpc(srv, "tools/call",
                         {"name": "ctx_recall", "arguments": {"query": "stripe rotated"}}))
        assert out["ok"] and "stripe" in out["hits"][0]["text"]

    def test_verify_tool(self, srv):
        out = _text(_rpc(srv, "tools/call",
                         {"name": "ctx_verify_text",
                          "arguments": {"text": "2 * 3 = 7 and it is guaranteed"}}))
        assert out["ok"] and out["verdict"] == "suspicious"

    def test_unknown_tool_is_isError(self, srv):
        resp = _rpc(srv, "tools/call", {"name": "nope", "arguments": {}})
        assert resp["result"]["isError"] is True

    def test_unknown_method_with_id_gets_error(self, srv):
        resp = _rpc(srv, "resources/list")
        assert resp["error"]["code"] == -32601

    def test_forget_tool(self, srv):
        mem_id = _text(_rpc(srv, "tools/call",
                            {"name": "ctx_remember", "arguments": {"text": "to delete"}}))["id"]
        out = _text(_rpc(srv, "tools/call",
                         {"name": "ctx_forget", "arguments": {"id": mem_id}}))
        assert out["ok"] is True

    def test_consensus_without_key_fails_cleanly(self, srv):
        out = _text(_rpc(srv, "tools/call",
                         {"name": "ctx_consensus",
                          "arguments": {"question": "q", "models": ["a", "b"]}}))
        # no env config → each transport call errors → report carries errors
        assert out["ok"] in (True, False)
        assert "error" in out or out.get("verdict") == "error" or out["ok"] is False


class TestStdioEndToEnd:
    def test_real_subprocess_session(self, tmp_path):
        """Drive a real `ctxkit serve` child over its own pipes.

        Note: pytest's fd-level capture can interact badly with a child that
        inherits stdout, so this test hands the child its own pipes and closes
        them explicitly in a finally block.
        """
        env = dict(os.environ, CTXKIT_HOME=str(tmp_path / "e2e"),
                   PYTHONPATH=SRC, PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            [sys.executable, "-m", "meshctx_ctxkit", "serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, text=True, bufsize=1)
        rc = None
        try:
            def send(obj):
                proc.stdin.write(json.dumps(obj) + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            init = send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2024-11-05"}})
            assert init["result"]["serverInfo"]["name"] == "ctxkit"

            # notification: no reply must be produced
            proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()

            tools = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            assert len(tools["result"]["tools"]) == 7

            remember = send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                             "params": {"name": "ctx_remember",
                                        "arguments": {"text": "e2e proof stored"}}})
            assert json.loads(remember["result"]["content"][0]["text"])["ok"] is True

            recall = send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "ctx_recall",
                                      "arguments": {"query": "e2e proof"}}})
            assert "e2e proof" in recall["result"]["content"][0]["text"]

            proc.stdin.close()
            rc = proc.wait(timeout=10)
        finally:
            for pipe in (proc.stdin, proc.stdout):
                try:
                    if pipe and not pipe.closed:
                        pipe.close()
                except OSError:
                    pass
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        assert rc == 0

    def test_server_main_importable(self):
        assert callable(server_main)
