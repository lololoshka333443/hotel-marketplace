"""Payment modes.

Phase 1 runs on STUB: the booking core must work end-to-end without a real
acquiring provider. Real acquiring (Tinkoff / YooKassa) plugs in later by
implementing the same `PaymentProvider` protocol.

`PAYMENT_MODE` selects the provider implementation at runtime.
"""

from enum import StrEnum


class PaymentMode(StrEnum):
    """`PAYMENT_MODE` values."""

    STUB = "stub"  # мгновенный успех — для разработки ядра
    DELAYED_STUB = "delayed_stub"  # успех через N секунд — для тестов hold TTL
    FAIL = "fail"  # всегда failed — для тестов веток ошибок
    TINKOFF = "tinkoff"  # реальный эквайринг (Phase 1.5+)


# Время искусственной задержки для DELAYED_STUB, секунд.
PAYMENT_STUB_DELAY_SEC = 30

VALID_MODES = {m.value for m in PaymentMode}
