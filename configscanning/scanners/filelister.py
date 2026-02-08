"""This scanner is for testing. It simply lists the names of the files it's asked to scan,
one per line, adding them to visited_files"""

from typing import Any

visited_files = []


class Scanner:
    def __init__(self, **kwargs: Any) -> None:
        pass

    def scan_file(self, fname: Any, data: Any) -> None:
        visited_files.append(fname)

    def finish(self) -> None:
        pass
