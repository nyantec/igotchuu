import subprocess

# TODO don't shell out

def create_snapshot(source, target, readonly=False):
    args = ["-r"] if readonly else []
    subprocess.run(["btrfs", "subvolume", "snapshot", *args, "--", source, target]).check_returncode()


def remove_snapshot(snapshot):
    subprocess.run(["btrfs", "subvolume", "delete", snapshot])
