from frontend.layout import is_phone_agent, resolve_mode

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
ANDROID = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)
ANDROID_TABLET = (
    "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def test_phones_are_detected_but_tablets_and_desktops_are_not():
    assert is_phone_agent(IPHONE)
    assert is_phone_agent(ANDROID)
    assert not is_phone_agent(ANDROID_TABLET)
    assert not is_phone_agent(MAC)
    assert not is_phone_agent("")


def test_query_parameter_overrides_the_device_and_is_remembered():
    assert resolve_mode({}, None, IPHONE) == "compact"
    assert resolve_mode({}, None, MAC) == "wide"
    assert resolve_mode({"layout": "wide"}, None, IPHONE) == "wide"
    assert resolve_mode({"layout": "compact"}, None, MAC) == "compact"
    # Page navigation drops the query string; the session keeps the earlier choice.
    assert resolve_mode({}, "compact", MAC) == "compact"
    assert resolve_mode({"layout": "bogus"}, None, MAC) == "wide"
