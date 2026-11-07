"""LOCAL_IPC: a Unix-domain socket is another process on this machine, never the network.

Every rule here is decided by something the dotted name cannot see -- the network argument
of `net.Dial`, the address family of `socket.socket`, the option `getsockopt` reads -- so
each positive case sits beside the negative that shares its name, and an argument the
source does not write as a constant is said as a blind spot rather than guessed (rule 1).
A boundary a signature names is **declared**, kept in its own table, and never counted as
a touch (rule 32).
"""
from __future__ import annotations

import shutil

import pytest

from dunneflow import ingest
from dunneflow.detectors import EVIDENCE_NOTE, RulesMissing, _refuse_unread_keys
from dunneflow.extractors.python.extract import extract_file
from dunneflow.ingest.acts import one_act
from dunneflow.schema import BoundaryHit, BoundaryKind, Direction, FileFacts

GO = ingest.PLUGINS.get("go")

GO_SOURCE = '''package p

import (
\t"net"
\t"syscall"
\t"time"

\t"golang.org/x/sys/unix"
)

const sock = "/run/p.sock"

func both(network string) {
\ta, _ := net.Dial("unix", sock)
\tb, _ := net.Dial("tcp", "example.com:80")
\tc, _ := net.Dial(network, "x")
\td, _ := net.DialTimeout("unix", "/tmp/s", 2*time.Second)
\t_, _, _, _ = a, b, c, d
}

func listeners(p string) {
\tl, _ := net.Listen("unix", p)
\tu, _ := net.ListenUnix("unix", &net.UnixAddr{Name: p, Net: "unix"})
\tc, _ := net.DialUnix("unix", nil, &net.UnixAddr{Name: sock, Net: "unix"})
\tc.WriteMsgUnix(nil, nil, nil)
\t_, _ = l, u
\tsyscall.Socket(syscall.AF_UNIX, syscall.SOCK_STREAM, 0)
\tsyscall.Socket(syscall.AF_INET, syscall.SOCK_STREAM, 0)
}

func peer(fd int) {
\tunix.GetsockoptUcred(fd, unix.SOL_SOCKET, unix.SO_PEERCRED)
\tunix.GetsockoptXucred(fd, unix.SOL_LOCAL, unix.LOCAL_PEERCRED)
\tunix.GetsockoptInt(fd, unix.SOL_SOCKET, unix.SO_RCVBUF)
}

func Listen(path string, gid int) (*net.UnixListener, error) { panic("stub") }
func PeerUID(c *net.UnixConn) (uint32, error)               { panic("stub") }
func Serve(l net.Listener)                                  { panic("stub") }
func Real(p string) (*net.UnixListener, error) {
\treturn net.ListenUnix("unix", &net.UnixAddr{Name: p, Net: "unix"})
}
'''


def _rows(ff: FileFacts) -> dict[tuple[str, int], list[BoundaryHit]]:
    names = {r.id: r.name for r in ff.routines}
    out: dict[tuple[str, int], list[BoundaryHit]] = {}
    for b in ff.boundaries:
        out.setdefault((names.get(b.routine_id, "?"), b.line), []).append(b)
    return out


@pytest.fixture(scope="module")
def go_ff(tmp_path_factory) -> FileFacts:
    if GO is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    root = tmp_path_factory.mktemp("goipc")
    (root / "go.mod").write_text("module example.com/p\n\ngo 1.22\n", encoding="utf-8")
    (root / "p.go").write_text(GO_SOURCE, encoding="utf-8")
    GO.probe()
    GO.open(root, [root / "p.go"])
    try:
        return next(iter(GO.extract([root / "p.go"], root)))
    finally:
        GO.close()


def _one(rows, routine: str, line: int) -> BoundaryHit:
    got = rows[(routine, line)]
    assert len(got) == 1, got
    return got[0]


def test_unix_and_tcp_in_one_file_are_told_apart_by_the_network_argument(go_ff):
    rows = _rows(go_ff)
    unix = _one(rows, "both", 14)
    assert (unix.kind, unix.direction, unix.target, unix.evidence) == (
        BoundaryKind.LOCAL_IPC, Direction.OUT, "sock", "net.Dial")
    tcp = _one(rows, "both", 15)
    assert tcp.kind is BoundaryKind.NETWORK and EVIDENCE_NOTE not in tcp.evidence
    timed = _one(rows, "both", 17)
    assert (timed.kind, timed.target) == (BoundaryKind.LOCAL_IPC, "/tmp/s")


def test_a_network_argument_that_is_not_a_literal_stays_network_and_says_so(go_ff):
    hit = _one(_rows(go_ff), "both", 16)
    assert hit.kind is BoundaryKind.NETWORK
    assert hit.evidence.startswith("net.Dial" + EVIDENCE_NOTE + "blind spot: ")


def test_a_unix_socket_is_not_a_remote_call(go_ff):
    """No `net_calls` row, so no protocol `TCP` and no NO_TIMEOUT on a socket file."""
    assert sorted(n.line for n in go_ff.network) == [15, 16]


def test_the_unix_constructors_listen_and_dial_with_the_path_as_target(go_ff):
    rows = _rows(go_ff)
    assert (_one(rows, "listeners", 22).direction, _one(rows, "listeners", 22).target) == (
        Direction.IN, "p")
    listen_unix = _one(rows, "listeners", 23)
    assert (listen_unix.kind, listen_unix.direction, listen_unix.target) == (
        BoundaryKind.LOCAL_IPC, Direction.IN, "p")
    dial_unix = _one(rows, "listeners", 24)
    assert (dial_unix.direction, dial_unix.target) == (Direction.OUT, "sock")


def test_file_passing_and_peer_credentials_are_said_in_the_evidence(go_ff):
    rows = _rows(go_ff)
    assert _one(rows, "listeners", 25).evidence == (
        "c.WriteMsgUnix" + EVIDENCE_NOTE + "can pass file descriptors (SCM_RIGHTS)")
    for line, call in ((32, "unix.GetsockoptUcred"), (33, "unix.GetsockoptXucred")):
        hit = _one(rows, "peer", line)
        assert (hit.kind, hit.direction, hit.evidence) == (
            BoundaryKind.LOCAL_IPC, Direction.IN, call + EVIDENCE_NOTE + "peer credentials")
    assert ("peer", 34) not in rows             # SO_RCVBUF is any socket's option


def test_a_raw_socket_is_local_only_for_the_unix_family(go_ff):
    rows = _rows(go_ff)
    assert _one(rows, "listeners", 27).kind is BoundaryKind.LOCAL_IPC
    assert ("listeners", 28) not in rows


def test_a_stub_s_signature_is_declared_and_a_body_that_shows_it_is_not(go_ff):
    rows = _rows(go_ff)
    listen = _one(rows, "Listen", 37)
    assert (listen.kind, listen.direction, listen.declared, listen.evidence) == (
        BoundaryKind.LOCAL_IPC, Direction.IN, True,
        "*net.UnixListener" + EVIDENCE_NOTE + "declared by signature")
    peer = _one(rows, "PeerUID", 38)
    assert (peer.kind, peer.target, peer.declared) == (BoundaryKind.LOCAL_IPC, "c", True)
    serve = _one(rows, "Serve", 39)
    assert serve.kind is BoundaryKind.NETWORK and "may be a Unix-domain socket" in serve.evidence
    real = [b for (name, _), bs in rows.items() if name == "Real" for b in bs]
    assert [(b.kind, b.declared) for b in real] == [(BoundaryKind.LOCAL_IPC, False)]


# ------------------------------------------------------------------- Python --- #

PY_SOURCE = '''import socket
SOCK = "/run/x.sock"
def server(path):
    s = socket.socket(socket.AF_UNIX); s.bind(path)
def client():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
        c.connect(SOCK)
def tcp(host):
    t = socket.socket(socket.AF_INET); t.connect((host, 80))
def unknown(fam):
    return socket.socket(fam)
def handed():
    return socket.socket(fileno=0)
def made_only():
    return socket.socket(family=socket.AF_UNIX)
def rebound(a, b):
    c = socket.socket(socket.AF_UNIX)
    c.connect(a)
    c = socket.socket(socket.AF_UNIX); c.connect(b)
def peer(c):
    return c.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
'''


@pytest.fixture(scope="module")
def py_ff(tmp_path_factory) -> FileFacts:
    root = tmp_path_factory.mktemp("pyipc")
    (root / "s.py").write_text(PY_SOURCE, encoding="utf-8")
    return extract_file(root / "s.py", root)


def test_python_bind_and_connect_on_a_unix_socket_carry_the_path(py_ff):
    rows = _rows(py_ff)
    bind = _one(rows, "server", 4)
    assert (bind.kind, bind.direction, bind.target, bind.evidence) == (
        BoundaryKind.LOCAL_IPC, Direction.IN, "path", "s.bind")
    connect = _one(rows, "client", 7)
    assert (connect.kind, connect.direction, connect.target) == (
        BoundaryKind.LOCAL_IPC, Direction.OUT, "SOCK")
    assert ("client", 6) not in rows            # the socket the connect was made on


def test_python_another_family_stays_network(py_ff):
    hit = _one(_rows(py_ff), "tcp", 9)
    assert hit.kind is BoundaryKind.NETWORK and EVIDENCE_NOTE not in hit.evidence


def test_python_a_family_the_source_does_not_name_is_a_blind_spot(py_ff):
    rows = _rows(py_ff)
    for routine, line in (("unknown", 11), ("handed", 13)):
        hit = _one(rows, routine, line)
        assert hit.kind is BoundaryKind.NETWORK
        assert EVIDENCE_NOTE + "blind spot: " in hit.evidence


def test_python_a_socket_made_and_never_bound_is_its_own_row(py_ff):
    hit = _one(_rows(py_ff), "made_only", 15)
    assert (hit.kind, hit.direction) == (BoundaryKind.LOCAL_IPC, Direction.BOTH)


def test_python_a_name_rebound_to_a_second_socket_keeps_the_first_one_spent(py_ff):
    """`c = socket(...)`, `c.connect(a)`, `c = socket(...)`: the second binding must not
    leave the first socket counted as made-and-never-used (rule 40)."""
    rows = [(line, b.direction) for (name, line), bs in _rows(py_ff).items()
            if name == "rebound" for b in bs]
    assert sorted(rows) == [(18, Direction.OUT), (19, Direction.OUT)]


def test_python_peer_credentials(py_ff):
    hit = _one(_rows(py_ff), "peer", 21)
    assert hit.evidence == "c.getsockopt" + EVIDENCE_NOTE + "peer credentials"
    assert not [n for n in py_ff.network if n.line in (4, 7, 15, 17, 18, 19, 21)]


# ------------------------------------------------------------------ grammar --- #

def test_a_conditioned_rule_is_refused_by_a_reader_that_does_not_read_it(tmp_path):
    """Rule 49: a reader ignores a key it does not know, so a `when_arg` rule handed to it
    would match unconditionally and `net.Dial("tcp", a)` would be LOCAL_IPC."""
    data = {"boundaries": [{"kind": "LOCAL_IPC", "exact": ["x.y"],
                            "when_arg": {"index": 0, "in": ["unix"]}}]}
    with pytest.raises(RulesMissing, match="when_arg"):
        _refuse_unread_keys("kotlin", data, tmp_path / "kotlin.yaml")
    _refuse_unread_keys("go", data, tmp_path / "go.yaml")       # Go says it reads it


def test_the_chain_fold_reads_through_a_note():
    """`acts.one_act` folds a chain by the call's spelling, which a note now follows."""
    ff = FileFacts(path="a.go", lang="go", module="a", content_hash="x")
    ff.boundaries = [
        BoundaryHit(routine_id="r", kind=BoundaryKind.LOCAL_IPC, direction=Direction.IN,
                    target="", line=3, evidence="c.ReadMsgUnix" + EVIDENCE_NOTE + "note"),
        BoundaryHit(routine_id="r", kind=BoundaryKind.LOCAL_IPC, direction=Direction.IN,
                    target="", line=3, evidence="c.ReadMsgUnix.Close" + EVIDENCE_NOTE + "note"),
    ]
    one_act(ff)
    assert [b.evidence.split(EVIDENCE_NOTE)[0] for b in ff.boundaries] == ["c.ReadMsgUnix"]


def test_a_declared_boundary_is_stored_apart_from_every_touch(tmp_path):
    """Rule 32: 45 queries count or detect `boundaries`; a claim about intent is not one."""
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    if GO is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    root = tmp_path / "t"
    root.mkdir()
    (root / "go.mod").write_text("module example.com/p\n\ngo 1.22\n", encoding="utf-8")
    (root / "p.go").write_text(GO_SOURCE, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    touches = store.query("SELECT evidence FROM boundaries")
    declared = store.query("SELECT kind, evidence FROM declared_boundaries ORDER BY line")
    counts = store.counts()
    store.close()
    assert not [r for r in touches if "declared by signature" in r["evidence"]]
    assert [r["kind"] for r in declared] == ["LOCAL_IPC", "LOCAL_IPC", "NETWORK"]
    assert counts["declared_boundaries"] == 3


# ---------------------------------------------- the other four readers, 2026-11-07 --- #
# LOCAL_IPC was taught to Go and Python first. C and C++ read `socket(AF_UNIX, ...)` as
# NETWORK, Kotlin read `java.net.UnixDomainSocketAddress.of` as NETWORK through its
# `java.net.` prefix, and Rust and Java recorded no Unix socket at all.

def _read(lang: str, files: dict[str, str], tmp_path_factory) -> dict[str, FileFacts]:
    from dunneflow.ingest.contract import ToolchainMissing

    plugin = ingest.PLUGINS.get(lang)
    if plugin is None:
        pytest.skip(f"this build ships no {lang} reader")
    try:
        plugin.probe()
    except ToolchainMissing as exc:
        pytest.skip(f"no {lang} toolchain on this machine: {exc}")
    root = tmp_path_factory.mktemp(f"ipc{lang}")
    paths = []
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
        paths.append(root / name)
    plugin.open(root, paths)
    try:
        return {ff.path: ff for ff in plugin.extract(paths, root)}
    finally:
        plugin.close()


def _by_line(ff: FileFacts) -> dict[int, list[tuple[str, str, str]]]:
    out: dict[int, list[tuple[str, str, str]]] = {}
    for b in ff.boundaries:
        out.setdefault(b.line, []).append((b.kind.value, b.target, b.evidence))
    return out


C_SOURCE = """#include <sys/socket.h>

int unix_client(void) { return socket(AF_UNIX, SOCK_STREAM, 0); }
int tcp_client(void) { return socket(AF_INET, SOCK_STREAM, 0); }
int either(int fam) { return socket(fam, SOCK_STREAM, 0); }
int pair(int sv[2]) { return socketpair(AF_UNIX, SOCK_STREAM, 0, sv); }
"""


def test_c_decides_a_socket_on_its_family_and_an_ipv4_one_says_nothing(tmp_path_factory):
    rows = _by_line(_read("cpp", {"p.c": C_SOURCE}, tmp_path_factory)["p.c"])
    assert rows[3] == [("LOCAL_IPC", "", "socket")]
    # NETWORK's target is its argument 0, which for `socket` is the family, as before.
    assert rows[4] == [("NETWORK", "AF_INET", "socket")], "not_in: decided, not a blind spot"
    assert rows[5] == [("NETWORK", "fam", "socket" + EVIDENCE_NOTE + "blind spot: the address "
                        "family is not written as AF_UNIX, so a Unix-domain socket here "
                        "reads as NETWORK")]
    assert rows[6] == [("LOCAL_IPC", "", "socketpair")]


RUST_SOURCE = """use std::os::unix::net::{UnixDatagram, UnixListener, UnixStream};

fn client(p: &str) { let _s = UnixStream::connect(p); }
fn server(p: &str) { let _l = UnixListener::bind(p); }
async fn tok(p: &str) { let _s = tokio::net::UnixStream::connect(p).await; }
fn pair() { let _q = UnixStream::pair(); let _d = UnixDatagram::bind("/tmp/d"); }
fn tcp(a: &str) { let _t = std::net::TcpStream::connect(a); }
fn main() {}
"""


def test_rust_names_a_unix_socket_by_its_type(tmp_path_factory):
    ff = _read("rust", {"Cargo.toml": '[package]\nname = "p"\nversion = "0.1.0"\n',
                        "src/main.rs": RUST_SOURCE}, tmp_path_factory)["src/main.rs"]
    rows = _by_line(ff)
    assert rows[3] == [("LOCAL_IPC", "p", "UnixStream.connect")]
    assert rows[4] == [("LOCAL_IPC", "p", "UnixListener.bind")]
    assert rows[5] == [("LOCAL_IPC", "p", "tokio.net.UnixStream.connect")]
    assert sorted(rows[6]) == [("LOCAL_IPC", "", "UnixStream.pair"),
                               ("LOCAL_IPC", "/tmp/d", "UnixDatagram.bind")]
    assert rows[7] == [("NETWORK", "a", "std.net.TcpStream.connect")]
    assert [n.line for n in ff.network] == [7], "a Unix socket is not a remote call"


JAVA_SOURCE = """import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;

class P {
    void client(String p) throws Exception {
        var a = UnixDomainSocketAddress.of(p);
        SocketChannel c = SocketChannel.open(StandardProtocolFamily.UNIX);
        ServerSocketChannel s = ServerSocketChannel.open(StandardProtocolFamily.UNIX);
    }
    void tcp(java.net.InetSocketAddress a) throws Exception {
        SocketChannel.open(a);
        SocketChannel.open();
    }
}
"""


def test_java_decides_a_channel_on_its_family_and_names_a_unix_address(tmp_path_factory):
    rows = _by_line(_read("java", {"P.java": JAVA_SOURCE}, tmp_path_factory)["P.java"])
    assert rows[8] == [("LOCAL_IPC", "p", "UnixDomainSocketAddress.of")]
    assert rows[9] == [("LOCAL_IPC", "", "SocketChannel.open")]
    assert rows[10] == [("LOCAL_IPC", "", "ServerSocketChannel.open")]
    # A variable is NETWORK with no blind spot: every TCP channel would carry one (rule 43).
    assert rows[13] == [("NETWORK", "a", "SocketChannel.open")]
    assert rows[14] == [("NETWORK", "", "SocketChannel.open")]


KOTLIN_SOURCE = """import java.net.UnixDomainSocketAddress

fun client(p: String) {
    val a = UnixDomainSocketAddress.of(p)
    val b = java.net.UnixDomainSocketAddress.of(p)
}
"""


def test_kotlin_s_java_net_prefix_does_not_make_a_unix_address_the_network(tmp_path_factory):
    """Rule 40: Kotlin records every rule that matches, so LOCAL_IPC must end it."""
    rows = _by_line(_read("kotlin", {"P.kt": KOTLIN_SOURCE}, tmp_path_factory)["P.kt"])
    assert rows[4] == [("LOCAL_IPC", "p", "UnixDomainSocketAddress.of")]
    assert rows[5] == [("LOCAL_IPC", "p", "java.net.UnixDomainSocketAddress.of")]


TS_SOURCE = """import * as net from "net";

export function a(p: string) { return net.connect(p); }
export function b(p: string) { return net.createConnection({ path: p }); }
export function c() { return net.connect(8080, "localhost"); }
export function d() { return net.connect({ port: 80, host: "example.com" }); }
export function e(x: any) { return net.connect(x); }
export function f() { return net.connect("/run/s.sock"); }
"""


def test_node_decides_a_connection_by_its_first_argument_s_shape(tmp_path_factory):
    """A string is a path, a number a port, and an options object is a Unix socket when it
    sets `path`. A typed variable is decided by its type; an `any` cannot be."""
    ff = _read("typescript", {"p.ts": TS_SOURCE}, tmp_path_factory)["p.ts"]
    rows = _by_line(ff)
    assert rows[3] == [("LOCAL_IPC", "p", "net.connect")], "p: string is a path"
    assert rows[4] == [("LOCAL_IPC", "p", "net.createConnection")]
    assert rows[5] == [("NETWORK", "8080", "net.connect")]
    assert rows[6] == [("NETWORK", "example.com", "net.connect")]
    assert rows[7] == [("NETWORK", "x", "net.connect" + EVIDENCE_NOTE + "blind spot: the first "
                        "argument is not written as a path or an options object, so a "
                        "Unix-domain socket here reads as NETWORK")]
    assert rows[8] == [("LOCAL_IPC", "/run/s.sock", "net.connect")]
    assert ff.network == [], "a Unix socket is not a remote call, and net.connect is no library"
