import os
import subprocess
import json


class Restic(subprocess.Popen):
    @classmethod
    def backup(cls, places=[], extra_args=[], env=os.environ, **kwargs):
        return cls(
            args=["restic", "backup", *extra_args, "--json", "--", *places],
            stdout=subprocess.PIPE,
            #stdin=subprocess.DEVNULL,
            text=True,
            env={"RESTIC_PROGRESS_FPS": "4", **env},
            **kwargs
        )

    def progress_iter(self):
        while True:
            line = self.stdout.readline()
            if len(line) > 0:
                progress = json.loads(line)
                yield progress
                if progress["message_type"] == "summary":
                    return self.wait()
            else:
                returncode = self.poll()
                if returncode is not None:
                    return returncode
