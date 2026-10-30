"""Create a NEW controlled Git fixture with the withdrawal function staged."""
import argparse
from pathlib import Path
import shutil
import subprocess


def create_demo(destination: Path) -> None:
    # Refuse an existing destination, so no existing repository can be modified.
    destination.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "init", "-q", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "-c", "user.name=Ghost Demo",
                    "-c", "user.email=demo@example.invalid", "-c", "core.hooksPath=/dev/null",
                    "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "Empty demo baseline"], check=True)
    for name in ("bank.py", "test_bank.py"):
        shutil.copyfile(Path(__file__).parent / "withdrawal" / name, destination / name)
    subprocess.run(["git", "-C", str(destination), "add", "--", "bank.py", "test_bank.py"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New directory; must not already exist")
    args = parser.parse_args()
    try:
        create_demo(args.destination)
    except (OSError, subprocess.CalledProcessError):
        parser.exit(2, "Demo setup failed; destination must be new and Git must be available.\n")
    print("Created controlled fixture with an empty HEAD and staged function/tests.")
