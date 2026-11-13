import time
from pathlib import Path

from core.imysdb.imydb import IMYDB as _IMYDB


class IMYDB(_IMYDB):
    """IMYDB + quarantine unreadable files instead of crashing the bot."""

    def load_data(self) -> None:
        try:
            super().load_data()
        except (ValueError, TypeError) as exc:
            self.file_path = Path(self.file_path)
            backup = self.file_path.with_name(
                f"{self.file_path.name}.corrupt-{int(time.time())}"
            )
            self.file_path.replace(backup)
            print(f"Warning: {self.file_path} is unreadable ({exc}); moved to {backup}, starting empty.")
            self.data = {}
            self.save_data()
