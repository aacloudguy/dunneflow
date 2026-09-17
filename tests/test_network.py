"""Remote calls carry more signature than local ones, and it must be captured."""

from __future__ import annotations


def test_remote_call_records_protocol_and_verb(analyzed):
    rows = analyzed.query(
        "SELECT protocol, verb, timeout, payload FROM net_calls WHERE expr LIKE 'requests%'"
    )
    assert rows
    r = rows[0]
    assert r["protocol"] == "HTTP"
    assert r["verb"] == "POST"
    assert r["timeout"] == "5.0"
    assert r["payload"]


def test_sync_library_is_marked_blocking(analyzed):
    row = analyzed.query(
        "SELECT is_async, awaited FROM net_calls WHERE expr LIKE 'requests%'"
    )[0]
    assert not row["is_async"] and not row["awaited"]


def test_async_libraries_are_distinguished_from_sync():
    from dunneflow.detectors import load_rules

    r = load_rules("python")
    assert r.network_profile("httpx.AsyncClient.post") == ("HTTP", True)
    assert r.network_profile("httpx.Client.post") == ("HTTP", False)
    assert r.network_profile("aiohttp.ClientSession.get") == ("HTTP", True)


def test_messaging_protocols_are_named_precisely():
    from dunneflow.detectors import load_rules

    r = load_rules("python")
    assert r.network_profile("pika.BlockingConnection")[0] == "AMQP"
    assert r.network_profile("aiokafka.AIOKafkaProducer") == ("Kafka", True)
    assert r.network_profile("paho.mqtt.client.Client")[0] == "MQTT"


def test_subprocess_poll_is_not_a_queue_consumer():
    """`proc.poll()` checks an exit status; it is not a broker read."""
    from dunneflow.detectors import load_rules

    rule = load_rules("python").match_call("self.proc.poll")
    assert rule is None or rule.kind.value != "QUEUE"


def test_http_handler_method_is_an_inbound_entrypoint(tmp_path):
    from pathlib import Path

    from dunneflow.extractors.python.extract import extract_file

    src = (
        "from http.server import BaseHTTPRequestHandler\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def do_POST(self):\n"
        "        pass\n"
    )
    f = tmp_path / "srv.py"
    f.write_text(src, encoding="utf-8")
    facts = extract_file(Path(f), tmp_path)
    kinds = {(e.kind.value, e.name) for e in facts.entrypoints}
    assert ("HTTP_ROUTE", "H.do_POST") in kinds
