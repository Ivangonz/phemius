"""Voice synthesis runs one call at a time, for narration and previews alike.

Local voice models are heavy enough that two at once can exhaust memory. The
lock is held per call, not per job, so a preview waits for at most one section
of a long narration.
"""

import threading

lock = threading.Lock()
