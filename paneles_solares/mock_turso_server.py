"""
Servidor HTTP local que habla el mismo protocolo Hrana v2 (/v2/pipeline)
que usa db_conn.ClienteTursoHTTP, respaldado por una base sqlite3 real.
Permite probar el cliente de punta a punta (codificación de valores,
batch, errores) sin tener acceso a la red real de Turso.
"""
import base64
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN_VALIDO = "test-token-123"


def _valor_a_hrana(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode("ascii")}
    return {"type": "text", "value": str(v)}


def _valor_de_hrana(d):
    tipo = d.get("type")
    if tipo == "null":
        return None
    if tipo == "integer":
        return int(d["value"])
    if tipo == "float":
        return float(d["value"])
    if tipo == "text":
        return d["value"]
    if tipo == "blob":
        return base64.b64decode(d["base64"])
    return d.get("value")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silencio en los tests

    def do_POST(self):
        auth = self.headers.get("Authorization", "")
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo)

        if auth != f"Bearer {TOKEN_VALIDO}":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Invalid auth token"}).encode())
            return

        if self.path != "/v2/pipeline":
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": f"Unknown path {self.path}"}).encode())
            return

        try:
            payload = json.loads(cuerpo)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"message": "invalid json"}')
            return

        conn = self.server.conn  # sqlite3 compartida del server de prueba
        resultados = []
        for req in payload.get("requests", []):
            if req["type"] == "close":
                resultados.append({"type": "ok", "response": {"type": "close"}})
                continue
            if req["type"] != "execute":
                resultados.append({"type": "error",
                                    "error": {"message": f"tipo no soportado: {req['type']}",
                                              "code": "UNSUPPORTED"}})
                continue

            stmt = req["stmt"]
            sql = stmt["sql"]
            args = [_valor_de_hrana(a) for a in stmt.get("args", [])]
            try:
                cur = conn.execute(sql, args)
                filas = cur.fetchall()
                conn.commit()
                cols = [{"name": d[0]} for d in (cur.description or [])]
                rows_hrana = [[_valor_a_hrana(v) for v in fila] for fila in filas]
                resultados.append({
                    "type": "ok",
                    "response": {
                        "type": "execute",
                        "result": {
                            "cols": cols,
                            "rows": rows_hrana,
                            "affected_row_count": cur.rowcount if cur.rowcount >= 0 else 0,
                            "last_insert_rowid": str(cur.lastrowid) if cur.lastrowid else None,
                        }
                    }
                })
            except sqlite3.IntegrityError as e:
                resultados.append({"type": "error",
                                    "error": {"message": str(e), "code": "SQLITE_CONSTRAINT"}})
            except sqlite3.OperationalError as e:
                resultados.append({"type": "error",
                                    "error": {"message": str(e), "code": "SQLITE_ERROR"}})

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"baton": None, "results": resultados}).encode())


def iniciar_servidor_en_hilo(puerto=0):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    server = HTTPServer(("127.0.0.1", puerto), Handler)
    server.conn = conn
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    return server, server.server_port
