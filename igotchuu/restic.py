# Copyright © 2022 nyantec GmbH <oss@nyantec.com>
# Written by Vika Shleina <vsh@nyantec.com>
#
# Provided that these terms and disclaimer and all copyright notices
# are retained or reproduced in an accompanying document, permission
# is granted to deal in this work without restriction, including un‐
# limited rights to use, publicly perform, distribute, sell, modify,
# merge, give away, or sublicence.
#
# This work is provided "AS IS" and WITHOUT WARRANTY of any kind, to
# the utmost extent permitted by applicable law, neither express nor
# implied; without malicious intent or gross negligence. In no event
# may a licensor, author or contributor be held liable for indirect,
# direct, other damage, loss, or other issues arising in any way out
# of dealing in the work, even if advised of the possibility of such
# damage or existence of a defect, except proven that it results out
# of said person's immediate fault when using the work as intended.
import os
import subprocess
import json


class Restic(subprocess.Popen):
    @classmethod
    def backup(
            cls, places=[], extra_args=[], env=dict(os.environ),
            repo=None, password_file=None, repository_file=None, password_command=None,
            **kwargs
    ):
        if repo is not None:
            env["RESTIC_REPOSITORY"] = repo
        if password_file is not None:
            env['RESTIC_PASSWORD_FILE'] = password_file
        if repository_file is not None:
            env['RESTIC_REPOSITORY_FILE'] = repository_file
        if password_command is not None:
            env['RESTIC_PASSWORD_COMMAND'] = password_command

        env["RESTIC_PROGRESS_FPS"] = "4"

        return cls(
            args=["restic", "backup", *extra_args, "--json", "--", *places],
            stdout=subprocess.PIPE, text=True, env=env, **kwargs
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
