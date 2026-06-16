"""Simplicio — AI coding agent that saves up to 96% on tokens."""

__version__ = "1.0.0"

def main():
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "simplicio"] + sys.argv[1:])
