"""Small dependency-free health probe shared by Python service images."""

import sys
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        return 2

    try:
        with urllib.request.urlopen(sys.argv[1], timeout=5) as response:
            return 0 if 200 <= response.status < 300 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
