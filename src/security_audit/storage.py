"""Private broker-side JSONL storage; no agent-accessible read endpoint."""

import json
import os
from pathlib import Path

DEFAULT_LOG = '/tmp/security-audit.jsonl'


class AuditWriter:
    def __init__(self, path=DEFAULT_LOG):
        self.pending = Path(str(path) + '.pending')
        self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.failed = False

    def append(self, event):
        if self.failed:
            return False
        try:
            # The observer must not accept a complete-looking line after failed fsync.
            pending_fd = os.open(self.pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(pending_fd)
            data = (json.dumps(event, ensure_ascii=True) + '\n').encode('utf-8')
            offset = 0
            while offset < len(data):
                count = os.write(self.fd, data[offset:])
                if not count:
                    raise OSError('Audit write failed')
                offset += count
            os.fsync(self.fd)
            self.pending.unlink()
            return True
        except OSError:
            # Do not append after a partial line or claim the operation was rolled back.
            self.failed = True
            return False

    def close(self):
        os.close(self.fd)
