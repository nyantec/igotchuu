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
