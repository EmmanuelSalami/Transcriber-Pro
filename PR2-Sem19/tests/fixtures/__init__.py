"""Test fixtures for unit tests."""

# Import all fixtures to make them available
from tests.fixtures.core import *  # noqa: F401, F403
from tests.fixtures.models import *  # noqa: F401, F403

try:
    from tests.fixtures.jobs import *  # noqa: F401, F403
except ImportError:
    pass  # Jobs fixtures may have dependencies that aren't available
try:
    from tests.fixtures.api import *  # noqa: F401, F403
except ImportError:
    pass  # API fixtures may have dependencies that aren't available
try:
    from tests.fixtures.media import *  # noqa: F401, F403
except ImportError:
    pass  # Media fixtures may have dependencies that aren't available
try:
    from tests.fixtures.infrastructure import *  # noqa: F401, F403
except ImportError:
    pass  # Infrastructure fixtures may have dependencies that aren't available
try:
    from tests.fixtures.transcription import *  # noqa: F401, F403
except ImportError:
    pass  # Transcription fixtures may have dependencies that aren't available
try:
    from tests.fixtures.utils import *  # noqa: F401, F403
except ImportError:
    pass  # Utils fixtures may have dependencies that aren't available
