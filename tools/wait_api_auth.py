"""Sonde GET /v1/auth/me — usage launcher_web_auth.bat."""
from __future__ import annotations

import socket
import sys
import urllib.error
import urllib.request

AUTH_ME_URL = "http://127.0.0.1:8000/v1/auth/me"

# Codes de sortie :
#   0 = auth ON (401 sans token)
#   1 = API injoignable / erreur inattendue
#   2 = API repond 200 => auth OFF (mauvaise instance sur :8000)
#   3 = port 8000 deja ouvert mais API pas encore pret


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def probe_auth_me() -> int:
    try:
        urllib.request.urlopen(AUTH_ME_URL, timeout=2)
    except urllib.error.HTTPError as exc:
        return 0 if exc.code == 401 else 1
    except urllib.error.URLError:
        return 1
    except Exception:
        return 1
    return 2


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--port-only":
        sys.exit(0 if port_open("127.0.0.1", 8000) else 1)
    sys.exit(probe_auth_me())


if __name__ == "__main__":
    main()
