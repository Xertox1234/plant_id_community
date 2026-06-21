"""Trusted-proxy client-IP resolution for per-IP rate limiting (todo 218).

Pins the behavior of ``get_trusted_client_ip`` / ``client_ip_key`` — the
replacement for django-ratelimit's ``key="ip"`` that resolves the real client
behind Railway's proxy from ``X-Forwarded-For``. The critical property is
spoofing rejection: a client-forged, left-prepended XFF entry must NOT change the
rate-limit key (otherwise an attacker rotates the key and bypasses the limit).
"""

from apps.core.ratelimit import client_ip_key, get_trusted_client_ip
from django.test import RequestFactory, SimpleTestCase, override_settings

CLIENT_IP = "203.0.113.7"  # the real client (TEST-NET-3, RFC 5737)
PROXY_IP = "10.0.0.1"  # an internal proxy hop
SPOOF_IP = "1.2.3.4"  # an attacker-supplied value


def _request(remote_addr="127.0.0.1", xff=None):
    extra = {"REMOTE_ADDR": remote_addr}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return RequestFactory().get("/", **extra)


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=0)
class ProxyCountZeroTests(SimpleTestCase):
    """Default (no trusted proxy): keep dev/test on REMOTE_ADDR, ignore XFF."""

    def test_ignores_xff_uses_remote_addr(self):
        req = _request(remote_addr="198.51.100.9", xff=CLIENT_IP)
        self.assertEqual(get_trusted_client_ip(req), "198.51.100.9")

    def test_key_matches_remote_addr(self):
        req = _request(remote_addr="198.51.100.9", xff=CLIENT_IP)
        self.assertEqual(client_ip_key(None, req), "198.51.100.9")


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1)
class OneTrustedProxyTests(SimpleTestCase):
    """One trusted hop (Railway edge = REMOTE_ADDR), client appended to XFF."""

    def test_single_xff_entry_is_the_client(self):
        req = _request(remote_addr=PROXY_IP, xff=CLIENT_IP)
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)

    def test_spoofed_left_prepend_is_ignored(self):
        # Attacker pre-sets XFF; the trusted proxy then appends the real client,
        # so the spoof lands to the LEFT and the rightmost (trusted) entry wins.
        req = _request(remote_addr=PROXY_IP, xff=f"{SPOOF_IP}, {CLIENT_IP}")
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)

    def test_spoof_cannot_rotate_the_key(self):
        # Two requests from the same real client with DIFFERENT forged prefixes
        # must resolve to the SAME key — otherwise the limit is trivially evaded.
        a = _request(remote_addr=PROXY_IP, xff=f"{SPOOF_IP}, {CLIENT_IP}")
        b = _request(remote_addr=PROXY_IP, xff=f"9.9.9.9, {CLIENT_IP}")
        self.assertEqual(client_ip_key(None, a), client_ip_key(None, b))
        self.assertEqual(client_ip_key(None, a), CLIENT_IP)

    def test_no_xff_falls_back_to_remote_addr(self):
        req = _request(remote_addr=PROXY_IP, xff=None)
        self.assertEqual(get_trusted_client_ip(req), PROXY_IP)

    def test_invalid_ip_in_trusted_position_falls_back(self):
        req = _request(remote_addr=PROXY_IP, xff="not-an-ip-address")
        self.assertEqual(get_trusted_client_ip(req), PROXY_IP)

    def test_ip_with_port_in_trusted_position_falls_back(self):
        # Pins M1 (todo 218): if the proxy appends "client:port" instead of a bare
        # IP, ipaddress.ip_address rejects it and we fall back to REMOTE_ADDR. This
        # is SAFE (the result is the server-set proxy address, never the
        # attacker-influenced string) but it OVER-THROTTLES — every client collapses
        # into the single REMOTE_ADDR bucket. The live-verification step MUST confirm
        # the prod proxy appends a bare IP, or strip the port before relying on this.
        req = _request(remote_addr=PROXY_IP, xff=f"{CLIENT_IP}:8080")
        self.assertEqual(get_trusted_client_ip(req), PROXY_IP)

    def test_bracketed_ipv6_with_port_in_trusted_position_falls_back(self):
        # Same M1 caveat for the bracketed IPv6 + port form "[2001:db8::1]:443".
        req = _request(remote_addr=PROXY_IP, xff="[2001:db8::1]:443")
        self.assertEqual(get_trusted_client_ip(req), PROXY_IP)


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
class TwoTrustedProxiesTests(SimpleTestCase):
    """Two trusted hops: client is the entry two from the right."""

    def test_client_is_second_from_right(self):
        # XFF = client, proxy1 ; REMOTE_ADDR = proxy2 (the last hop, not in XFF).
        req = _request(remote_addr="10.0.0.2", xff=f"{CLIENT_IP}, {PROXY_IP}")
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)

    def test_spoofed_prepend_still_ignored(self):
        req = _request(
            remote_addr="10.0.0.2", xff=f"{SPOOF_IP}, {CLIENT_IP}, {PROXY_IP}"
        )
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)

    def test_fewer_entries_than_proxy_count_falls_back(self):
        # Only one XFF entry but two proxies expected → a hop is missing; do not
        # trust the lone entry, fall back to REMOTE_ADDR.
        req = _request(remote_addr="10.0.0.2", xff=CLIENT_IP)
        self.assertEqual(get_trusted_client_ip(req), "10.0.0.2")


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1)
class IPv6MaskingTests(SimpleTestCase):
    """IPv6 is masked to /64 (django-ratelimit's default), so a client cannot
    rotate the low 64 bits to a fresh /128 per request and evade the limit."""

    def test_addresses_in_one_64_share_a_bucket(self):
        a = _request(remote_addr=PROXY_IP, xff="2001:db8:abcd:1234::5")
        b = _request(remote_addr=PROXY_IP, xff="2001:db8:abcd:1234::99ff")
        self.assertEqual(client_ip_key(None, a), client_ip_key(None, b))

    def test_masks_to_network_address(self):
        req = _request(remote_addr=PROXY_IP, xff="2001:db8:abcd:1234::5")
        self.assertEqual(client_ip_key(None, req), "2001:db8:abcd:1234::")

    def test_different_64s_get_different_buckets(self):
        a = _request(remote_addr=PROXY_IP, xff="2001:db8:abcd:1234::5")
        b = _request(remote_addr=PROXY_IP, xff="2001:db8:abcd:5678::5")
        self.assertNotEqual(client_ip_key(None, a), client_ip_key(None, b))

    def test_ipv4_is_not_masked(self):
        # /32 default → no-op; the full IPv4 address is the key.
        req = _request(remote_addr=PROXY_IP, xff=CLIENT_IP)
        self.assertEqual(client_ip_key(None, req), CLIENT_IP)


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1)
class UnknownBucketTests(SimpleTestCase):
    """When no IP can be resolved, key falls into a single shared bucket."""

    def test_key_is_unknown_when_no_ip(self):
        req = _request(remote_addr="", xff=None)
        self.assertIsNone(get_trusted_client_ip(req))
        self.assertEqual(client_ip_key(None, req), "unknown")


ENVOY_META = "HTTP_X_ENVOY_EXTERNAL_ADDRESS"


@override_settings(
    RATELIMIT_CLIENT_IP_META_KEY=ENVOY_META, RATELIMIT_TRUSTED_PROXY_COUNT=1
)
class ClientIpMetaKeyTests(SimpleTestCase):
    """A configured single trusted header (e.g. Railway/Envoy) wins over XFF."""

    def test_header_value_is_used(self):
        req = RequestFactory().get("/", REMOTE_ADDR=PROXY_IP, **{ENVOY_META: CLIENT_IP})
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)

    def test_header_takes_precedence_over_xff(self):
        # XFF would resolve to SPOOF_IP under count=1, but the trusted header wins.
        req = RequestFactory().get(
            "/",
            REMOTE_ADDR=PROXY_IP,
            HTTP_X_FORWARDED_FOR=SPOOF_IP,
            **{ENVOY_META: CLIENT_IP},
        )
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)
        self.assertEqual(client_ip_key(None, req), CLIENT_IP)

    def test_missing_or_invalid_header_falls_back_to_remote_addr(self):
        # Header absent → REMOTE_ADDR (does NOT fall through to XFF when a meta key
        # is configured; the deployment is expected to set the header).
        req = RequestFactory().get(
            "/", REMOTE_ADDR=PROXY_IP, HTTP_X_FORWARDED_FOR=CLIENT_IP
        )
        self.assertEqual(get_trusted_client_ip(req), PROXY_IP)
        bad = RequestFactory().get("/", REMOTE_ADDR=PROXY_IP, **{ENVOY_META: "nope"})
        self.assertEqual(get_trusted_client_ip(bad), PROXY_IP)


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1, RATELIMIT_LOG_RESOLUTION=True)
class LogResolutionTests(SimpleTestCase):
    """The diagnostic log is side-effect-only — resolution is unchanged."""

    def test_resolution_unchanged_with_logging_on(self):
        req = _request(remote_addr=PROXY_IP, xff=CLIENT_IP)
        self.assertEqual(get_trusted_client_ip(req), CLIENT_IP)
        self.assertEqual(client_ip_key(None, req), CLIENT_IP)
