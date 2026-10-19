"""Linux descriptor-relative execution; no shell, link following, or overwrite."""

import os
from pathlib import PurePosixPath
import stat

from .schema import Rejected


class FileExecutor:
    def __init__(self, root="/lab"):
        self.root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.root_fd)

    def execute(self, tool, path, content, max_read_bytes):
        parts = PurePosixPath(path).relative_to('/lab').parts
        if not parts or any(p in ('.', '..') for p in parts):
            raise Rejected("INVALID_PATH")
        parent = os.dup(self.root_fd)
        fd = None
        try:
            for component in parts[:-1]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            if tool == "read_text":
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                metadata = os.fstat(fd)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise Rejected("UNSUPPORTED_OBJECT")
                if metadata.st_size > max_read_bytes:
                    raise Rejected("READ_LIMIT")
                data = b""
                while len(data) <= max_read_bytes:
                    chunk = os.read(fd, min(8192, max_read_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data += chunk
                if len(data) > max_read_bytes:
                    raise Rejected("READ_LIMIT")
                return {"text": data.decode("utf-8")}
            if tool != "write_new":
                raise Rejected("UNKNOWN_TOOL")
            data = content.encode("utf-8")
            fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            offset = 0
            while offset < len(data):
                count = os.write(fd, data[offset:])
                if count == 0:
                    raise OSError("Short write")
                offset += count
            os.fsync(fd)
            return {"bytes_written": offset}
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)
