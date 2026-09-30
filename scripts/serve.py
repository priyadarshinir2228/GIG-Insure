"""Start the GigInsure live platform (API, trigger monitor, admin dashboard and worker app)."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from giginsure.server import main

if __name__ == "__main__":
    main()
