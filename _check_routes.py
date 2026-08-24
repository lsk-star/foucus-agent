import sys
sys.path.insert(0, "src")

from pybase.application import create_application

app = create_application()

for route in app.routes:
    if hasattr(route, 'path'):
        print(f"  {route.path}  [{getattr(route, 'methods', '?')}]")
    else:
        print(f"  {type(route).__name__}")