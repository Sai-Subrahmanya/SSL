"""Smart Street Light V1 - digital prototype domain model.

EARLY ENGINEERING / DIGITAL PROTOTYPE DEVELOPMENT.

This package implements the engineering domain model described in
``docs/``. It is deterministic and hardware-independent: nothing here talks
to an MCU, a sensor, a UART, a flash chip or an RTC. Those concerns belong to
a later hardware abstraction layer.

Nothing in this package validates physical electrical safety, EMC, relay
life, RF performance, enclosure/IP rating, thermal performance, RTC backup
duration or certification.
"""

from .enums import *  # noqa: F401,F403  (re-exported for convenience)
from .errors import *  # noqa: F401,F403  (re-exported for convenience)

__version__ = "0.1.0"

__all__ = [
    "__version__",
]
