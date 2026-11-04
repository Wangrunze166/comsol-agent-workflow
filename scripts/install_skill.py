"""Copy the canonical skill into one project-local client directory; never overwrite."""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--client", choices=("codex", "claude", "cursor"), required=True)
parser.add_argument("--project", type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
client_dir = {"codex": ".agents", "claude": ".claude", "cursor": ".cursor"}[args.client]
destination = args.project.resolve() / client_dir / "skills/comsol-multiphysics"
if destination.exists():
    parser.error(f"Destination already exists; review/update it manually: {destination}")
shutil.copytree(repo / "skills/comsol-multiphysics", destination)
print(f"Copied skill to {destination}. Use the original workflow repository as the command working directory: {repo}")
