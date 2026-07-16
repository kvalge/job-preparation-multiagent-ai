from data.cv import save_cv
from data.db import save_cv_version


def save_cv_with_version(text: str) -> int:
    """Save the current CV (data/cv.txt) and snapshot it as a version. Returns version id.

    Used by the UI when the user saves/updates their CV, so every distinct CV state is
    recorded and can be referenced later by any analysis.
    """
    save_cv(text)
    return save_cv_version(text)


def ensure_cv_version(text: str) -> int:
    """Return the id of the CV version matching this text, snapshotting it if needed.

    Lets an analysis stamp the exact CV state it ran against, even for CVs that were
    saved before versioning existed.
    """
    return save_cv_version(text)
