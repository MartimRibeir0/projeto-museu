"""Envia um script Python ao Blender aberto (addon "MCP for Blender", porta 9876) e mostra o resultado.

Uso: python blender/send_to_blender.py blender/build_museum.py
     python blender/send_to_blender.py -c "print(bpy.app.version_string)"
"""

import json
import socket
import sys


def send(code: str, host: str = "127.0.0.1", port: int = 9876, timeout: float = 300) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(json.dumps({"type": "execute_code", "params": {"code": code}}).encode("utf-8"))
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # resposta incompleta
    raise ConnectionError("Blender fechou a ligação sem resposta")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "-c":
        code = sys.argv[2]
    elif len(sys.argv) == 2:
        import os

        path = os.path.abspath(sys.argv[1])
        with open(path, encoding="utf-8") as f:
            code = f"__file__ = {path!r}\n" + f.read()  # exec() no Blender não define __file__
    else:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")  # consola Windows em cp1252
    r = send(code)
    if r.get("status") != "success":
        sys.exit(json.dumps(r, indent=2, ensure_ascii=False))
    print(r["result"].get("result", r["result"]))
