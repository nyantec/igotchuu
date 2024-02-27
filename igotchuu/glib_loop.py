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
import threading
from gi.repository import GLib

class GLibMainLoopThread(threading.Thread):
    """A thread running the GLib main loop.

    Since GLib's main loop releases the GIL, work can continue on
    different Python threads with no problem."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.daemon = True
        self.mainloop = GLib.MainLoop.new(None, False)

    def run(self):
        self.mainloop.run()

    def quit(self):
        self.mainloop.quit()
