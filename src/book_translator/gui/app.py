from __future__ import annotations

import tkinter as tk

from .views import GuiShellViews, build_shell


class BookTranslatorGui:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.mode_var = tk.StringVar(master=self.root, value="engineering")
        self.views: GuiShellViews = build_shell(self.root, mode_var=self.mode_var)
        self.publishing_frame = self.views.publishing_frame
        self.mode_var.trace_add("write", self._on_mode_changed)
        self.sync_mode_panels()

    def run(self) -> None:
        self.root.mainloop()

    def sync_mode_panels(self) -> None:
        if self.mode_var.get() == "publishing":
            self.publishing_frame.grid()
        else:
            self.publishing_frame.grid_remove()
        self.root.update_idletasks()

    def _on_mode_changed(self, *_args: object) -> None:
        self.sync_mode_panels()


def main() -> None:
    app = BookTranslatorGui()
    app.run()
