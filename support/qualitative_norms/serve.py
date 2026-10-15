"""Local preview: python support/qualitative_norms/serve.py (no dependencies)."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8765)
parser.add_argument('--no-browser', action='store_true')
args = parser.parse_args()
handler = partial(SimpleHTTPRequestHandler, directory=str(Path(__file__).parent / 'dist'))
with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
    url = f'http://127.0.0.1:{args.port}'
    print(f'Normen-Werkbuch: {url}', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
