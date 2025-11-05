import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from mklogger import ActivityLogger
import time
import os
import threading
import csv

class TypingTestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Typing Test")

        self.test_text = (
            "The quick brown fox jumps over the lazy dog. "
            "Pack my box with five dozen liquor jugs."
        )

        self.initial_time = 120
        self.time_left = self.initial_time
        self.timer_job = None
        self.test_running = False
        self.timer_running = False
        self.start_time = None
        self._programmatic_edit = False
        self._last_typed = ""
        self._current_pos = 0
        self.current_test_file = "Default Text"
        self.current_test_display_var = tk.StringVar(value="Test: Default Text")

        # Programming mode state
        self.programming_mode = tk.BooleanVar(value=False)
        # Pair settings: opening -> (closing, enabled-var)
        self.pair_map: dict[str, tuple[str, tk.BooleanVar]] = {
            '(': (')', tk.BooleanVar(value=True)),
            '{': ('}', tk.BooleanVar(value=True)),
            '[': (']', tk.BooleanVar(value=True)),
            '"': ('"', tk.BooleanVar(value=True)),
            "'": ("'", tk.BooleanVar(value=True)),
        }

        self._build_ui()
        self._apply_text(self.test_text)
        self._update_timer_label()

        self.logger = ActivityLogger(log_file='typing_activity_log.txt')
        self.logger_thread = threading.Thread(target=self.logger.run, daemon=True)
        self.logger_thread.start()

    def _build_ui(self):
        # Styles and fonts
        self.ui_font = tkfont.Font(size=10)
        default_family = "Consolas" if self.root.tk.call('tk', 'windowingsystem') == 'win32' else (
            "Menlo" if self.root.tk.call('tk', 'windowingsystem') == 'aqua' else "DejaVu Sans Mono"
        )
        self.mono_font = tkfont.Font(family=default_family, size=13)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TButton", padding=(10, 6))
        style.configure("TLabel", font=self.ui_font)
        style.configure("Header.TLabel", font=tkfont.Font(size=10, weight="bold"))
        style.configure("Metric.TLabel", font=tkfont.Font(size=10, weight="bold"))

        top = ttk.Frame(self.root)
        top.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        controls = ttk.Frame(top)
        controls.pack(fill=tk.X, side=tk.TOP)

        ttk.Button(controls, text="Start Test", command=self.start_test).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Stop Test", command=self.stop_test).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Restart Test", command=self.restart_test).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12), pady=4)

        ttk.Button(controls, text="Load Test", command=self.load_test).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Save Test", command=self.save_test).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12), pady=4)

        ttk.Label(controls, text="Time (s):").pack(side=tk.LEFT)
        self.time_var = tk.StringVar(value=str(self.initial_time))
        self.time_select = ttk.Combobox(
            controls,
            textvariable=self.time_var,
            values=("15", "30", "60", "120", "180"),
            width=6,
            state="readonly",
        )
        self.time_select.pack(side=tk.LEFT, padx=(4, 12))

        self.timer_label = ttk.Label(controls, text="00:00", style="Header.TLabel")
        self.timer_label.pack(side=tk.LEFT)

        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(12, 12), pady=4)
        ttk.Checkbutton(controls, text="Programming Mode", variable=self.programming_mode).pack(side=tk.LEFT)
        ttk.Button(controls, text="Settings", command=self._open_programming_settings).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(top, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))

        self.top_frame = ttk.LabelFrame(top, text="Target Text")
        self.top_frame.pack(fill=tk.BOTH, expand=True)

        self.top_text = tk.Text(
            self.top_frame,
            wrap=tk.WORD,
            height=8,
            padx=8,
            pady=8,
            relief=tk.SUNKEN,
            font=self.mono_font,
        )
        self.top_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.top_text.tag_configure("correct", foreground="#16a34a")
        # Make mistakes highly visible: red background instead of red text
        self.top_text.tag_configure("incorrect", background="#fecaca")
        self.top_text.tag_configure("current", background="#facc15")

        self.bottom_frame = ttk.LabelFrame(top, text="Type Here (The test starts when you start typing.)")
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.input_text = tk.Text(
            self.bottom_frame,
            wrap=tk.WORD,
            height=6,
            padx=8,
            pady=8,
            relief=tk.SUNKEN,
            font=self.mono_font,
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.input_text.bind("<KeyRelease>", self._on_input_changed)
        # Intercept keypress for auto-close behavior (before default insertion)
        self.input_text.bind("<KeyPress>", self._on_keypress, add=True)
        # Keyboard shortcut: Ctrl+Backspace deletes previous word
        self.input_text.bind("<Control-BackSpace>", self._on_ctrl_backspace)
        # Tab inserts 4 spaces
        self.input_text.bind("<Tab>", self._on_tab_insert)
        self.top_text.bind("<Control-BackSpace>", self._on_ctrl_backspace)
        self.top_text.bind("<Tab>", self._on_tab_insert)

        results = ttk.Frame(top)
        results.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        self.wpm_var = tk.StringVar(value="WPM: 0.0")
        self.acc_var = tk.StringVar(value="Accuracy: 0.0%")
        self.time_taken_var = tk.StringVar(value="Time: 0.0s")

        self.status_font = tkfont.Font(size=12, weight="bold")
        self.status_label = tk.Label(
            results,
            textvariable=self.status_var,
            font=self.status_font,
            padx=10,
            pady=5,
        )
        self.status_label.pack(side=tk.LEFT)
        self._update_status_color("default")

        ttk.Label(results, textvariable=self.wpm_var).pack(side=tk.RIGHT)
        ttk.Label(results, textvariable=self.acc_var).pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(results, textvariable=self.time_taken_var).pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(results, textvariable=self.current_test_display_var).pack(side=tk.RIGHT, padx=(0, 12))

        self._set_editable(True)
        self._set_input_enabled(False)

        # Also bind at root to ensure the shortcut works consistently
        self.root.bind_all("<Control-BackSpace>", self._on_ctrl_backspace)

    def _update_status_color(self, state: str):
        color_map = {
            "running": ("#16a34a", "white"),  # green
            "stopped": ("#dc2626", "white"),  # red
            "pending": ("#facc15", "black"),  # yellow
            "default": ("#3b82f6", "white"),  # blue
        }
        bg, fg = color_map.get(state, ("white", "black"))
        self.status_label.config(bg=bg, fg=fg)

    def _set_editable(self, editable: bool):
        self.top_text.config(state=tk.NORMAL if editable else tk.DISABLED)

    def _set_input_enabled(self, enabled: bool):
        self.input_text.config(state=tk.NORMAL if enabled else tk.DISABLED)
        if enabled:
            self.input_text.focus_set()

    def _apply_text(self, text: str):
        state = self.top_text.cget("state")
        self.top_text.config(state=tk.NORMAL)
        self.top_text.delete("1.0", tk.END)
        self.top_text.insert("1.0", text)
        self.top_text.tag_remove("correct", "1.0", tk.END)
        self.top_text.tag_remove("incorrect", "1.0", tk.END)
        self.top_text.tag_remove("current", "1.0", tk.END)
        self.top_text.config(state=state)

    def _on_tab_insert(self, event):
        w = event.widget
        try:
            # Replace selection if present
            if w.tag_ranges("sel"):
                w.delete("sel.first", "sel.last")
            w.insert(tk.INSERT, "    ")
            # Keep typing flow consistent
            if w is self.input_text:
                self._on_input_changed()
            return "break"
        except Exception:
            return "break"

    def _on_keypress(self, event):
        # Only for input panel and when programming mode enabled
        if event.widget is not self.input_text:
            return None
        if not self.programming_mode.get():
            return None
        ch = event.char
        if not ch:
            return None
        pair = self.pair_map.get(ch)
        if not pair:
            return None
        closing, enabled_var = pair
        if not enabled_var.get():
            return None
        # Insert open+close and move cursor between them
        try:
            self._programmatic_edit = True
            # Replace selection if any
            if self.input_text.tag_ranges("sel"):
                self.input_text.delete("sel.first", "sel.last")
            idx = self.input_text.index(tk.INSERT)
            self.input_text.insert(idx, ch + closing)
            # place cursor between
            self.input_text.mark_set(tk.INSERT, f"{idx}+1c")
        finally:
            self._programmatic_edit = False
        # Update highlighting after insertion
        self._on_input_changed()
        return "break"

    def _open_programming_settings(self):
        d = tk.Toplevel(self.root)
        d.title("Programming Mode Settings")
        d.transient(self.root)
        d.grab_set()
        d.resizable(False, False)

        frm = ttk.Frame(d, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Auto-close pairs:").pack(anchor="w", pady=(0, 6))

        # Create checkboxes for each pair
        for opening, (closing, var) in self.pair_map.items():
            txt = f"{opening}{closing}"
            ttk.Checkbutton(frm, text=txt, variable=var).pack(anchor="w")

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Close", command=d.destroy).pack(side=tk.RIGHT)

    def _on_ctrl_backspace(self, event):
        widget = self.root.focus_get()
        # Helper to delete previous word from current insert position
        def delete_prev_word(w: tk.Text):
            try:
                insert_idx = w.index(tk.INSERT)
                if insert_idx == "1.0":
                    return
                # Skip whitespace to the left
                cur = insert_idx
                while True:
                    prev = w.index(f"{cur} -1c")
                    if prev == cur:
                        break
                    ch = w.get(prev)
                    if not ch.isspace():
                        cur = prev
                        break
                    cur = prev
                    if cur == "1.0":
                        break
                # Find start of the word from the current position
                word_start = w.index(f"{cur} wordstart")
                w.delete(word_start, insert_idx)
            except Exception:
                pass

        if widget == self.input_text:
            self._programmatic_edit = True
            delete_prev_word(self.input_text)
            self._programmatic_edit = False
            self._on_input_changed()
            return "break"
        if widget == self.top_text and not self.test_running:
            state = self.top_text.cget("state")
            self.top_text.config(state=tk.NORMAL)
            delete_prev_word(self.top_text)
            self.top_text.config(state=state)
            return "break"
        return None

    def _on_input_changed(self, _event=None):
        if not self.test_running:
            # Keep input cleared when not running
            self._programmatic_edit = True
            self.input_text.delete("1.0", tk.END)
            self._programmatic_edit = False
            return

        if self._programmatic_edit:
            return

        target = self.test_text
        typed = self.input_text.get("1.0", "end-1c")

        if not self.timer_running and typed:
            self._start_timer()

        # Allow typing beyond target; extra characters will not match and prevent completion

        self._update_highlighting_fast(typed, target)

        if typed == target:
            self._end_test(finished=True)

    def _update_highlighting(self, typed: str, target: str):
        state = self.top_text.cget("state")
        self.top_text.config(state=tk.NORMAL)
        self.top_text.tag_remove("correct", "1.0", tk.END)
        self.top_text.tag_remove("incorrect", "1.0", tk.END)
        self.top_text.tag_remove("current", "1.0", tk.END)

        n = min(len(typed), len(target))
        for i in range(n):
            tag = "correct" if typed[i] == target[i] else "incorrect"
            start = f"1.0+{i}c"
            end = f"1.0+{i+1}c"
            self.top_text.tag_add(tag, start, end)

        cur_index = len(typed)
        if cur_index < len(target):
            start = f"1.0+{cur_index}c"
            end = f"1.0+{cur_index+1}c"
            self.top_text.tag_add("current", start, end)

        self.top_text.config(state=state)

    # Fast/incremental highlighting helpers
    def _update_highlighting_fast(self, typed: str, target: str):
        prev = getattr(self, "_last_typed", "")
        state = self.top_text.cget("state")
        self.top_text.config(state=tk.NORMAL)

        if len(typed) == len(prev) + 1 and typed.startswith(prev):
            i = len(prev)
            if i < len(target):
                tag = "correct" if typed[i] == target[i] else "incorrect"
                self._tag_add(tag, i, i + 1)
                self._move_current(i + 1, len(target))
        elif len(typed) + 1 == len(prev) and prev.startswith(typed):
            i = len(typed)
            self._tag_remove_range(i, i + 1)
            self._move_current(i, len(target))
        else:
            self._retag_full(typed, target)

        self.top_text.config(state=state)
        self._last_typed = typed

    def _move_current(self, pos: int, target_len: int):
        prev_pos = getattr(self, "_current_pos", 0)
        if 0 <= prev_pos < target_len:
            self._tag_remove_specific("current", prev_pos, prev_pos + 1)
        self._current_pos = pos
        if 0 <= pos < target_len:
            self._tag_add("current", pos, pos + 1)

    def _tag_add(self, tag: str, start_i: int, end_i: int):
        self.top_text.tag_add(tag, f"1.0+{start_i}c", f"1.0+{end_i}c")

    def _tag_remove_specific(self, tag: str, start_i: int, end_i: int):
        self.top_text.tag_remove(tag, f"1.0+{start_i}c", f"1.0+{end_i}c")

    def _tag_remove_range(self, start_i: int, end_i: int):
        rng_start = f"1.0+{start_i}c"
        rng_end = f"1.0+{end_i}c"
        self.top_text.tag_remove("correct", rng_start, rng_end)
        self.top_text.tag_remove("incorrect", rng_start, rng_end)
        self.top_text.tag_remove("current", rng_start, rng_end)

    def _retag_full(self, typed: str, target: str):
        # Clear tags over the target length only
        self._tag_remove_range(0, len(target))
        n = min(len(typed), len(target))
        for i in range(n):
            tag = "correct" if typed[i] == target[i] else "incorrect"
            self._tag_add(tag, i, i + 1)
        self._move_current(n, len(target))

    def _update_timer_label(self):
        m, s = divmod(max(0, int(self.time_left)), 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")

    def _tick(self):
        if not self.timer_running:
            return
        self.time_left -= 1
        self._update_timer_label()
        if self.time_left <= 0:
            self._end_test(finished=False)
            return
        self.timer_job = self.root.after(1000, self._tick)

    def _start_timer(self):
        if self.timer_running:
            return
        self.timer_running = True
        self.start_time = time.time()
        self.timer_job = self.root.after(1000, self._tick)
        self.logger.start_logging()
        self._update_status_color("running")

    def _cancel_timer(self):
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except Exception:
                pass
        self.timer_job = None
        self.timer_running = False
        self.logger.stop_logging()


    def start_test(self):
        try:
            self.initial_time = int(self.time_var.get())
        except Exception:
            self.initial_time = 60
            self.time_var.set(str(self.initial_time))

        text = self.top_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Typing Test", "Please provide text to type (top panel).")
            return

        self.test_text = text
        self._apply_text(self.test_text)

        self.time_left = self.initial_time
        self._update_timer_label()
        self._cancel_timer()
        self.start_time = None

        self._programmatic_edit = True
        self.input_text.config(state=tk.NORMAL)
        self.input_text.delete("1.0", tk.END)
        self._programmatic_edit = False

        self._set_editable(False)
        self._set_input_enabled(True)

        self.wpm_var.set("WPM: 0.0")
        self.acc_var.set("Accuracy: 0.0%")
        self.time_taken_var.set("Time: 0.0s")
        self.status_var.set("Test running… Start typing!")
        self._update_status_color("pending")
        self.test_running = True
        self.timer_running = False

        # reset incremental-highlighting state
        self._last_typed = ""
        self._current_pos = 0
        # initialize tags for empty typed text
        try:
            self._retag_full("", self.test_text)
        except Exception:
            # fallback if helpers not yet defined at runtime ordering
            pass

    def restart_test(self):
        if not self.test_text.strip():
            return
        self._cancel_timer()
        self.test_running = False
        self.timer_running = False
        self.start_test()

    def stop_test(self):
        if not self.test_running:
            return
        # Stop timer and compute metrics using actual elapsed time
        self._cancel_timer()
        self.test_running = False
        end_time = time.time()
        elapsed = 0.0
        if self.start_time is not None:
            elapsed = end_time - self.start_time

        typed = self.input_text.get("1.0", "end-1c")
        target = self.test_text
        n = min(len(typed), len(target))
        correct = sum(1 for i in range(n) if typed[i] == target[i])
        total_typed = len(typed)
        accuracy = (correct / total_typed * 100.0) if total_typed > 0 else 0.0
        minutes = max(elapsed, 1e-9) / 60.0
        wpm = (correct / 5.0) / minutes if minutes > 0 else 0.0

        self.wpm_var.set(f"WPM: {wpm:.1f}")
        self.acc_var.set(f"Accuracy %: {accuracy:.1f}%")
        self.time_taken_var.set(f"Time: {elapsed:.1f}s")
        self.status_var.set("Stopped")
        self._update_status_color("stopped")

        self._log_stats_to_csv(wpm, accuracy, elapsed)
        self._set_input_enabled(False)
        self._set_editable(True)

    def _end_test(self, finished: bool):
        if not self.test_running:
            return
        self.test_running = False
        self._cancel_timer()

        end_time = time.time()
        elapsed = 0.0
        if self.start_time is not None:
            elapsed = end_time - self.start_time
        else:
            elapsed = 0.0

        if not finished and self.initial_time:
            elapsed = float(self.initial_time)

        typed = self.input_text.get("1.0", "end-1c")
        target = self.test_text
        n = min(len(typed), len(target))
        correct = sum(1 for i in range(n) if typed[i] == target[i])
        total_typed = len(typed)
        accuracy = (correct / total_typed * 100.0) if total_typed > 0 else 0.0

        minutes = max(elapsed, 1e-9) / 60.0
        wpm = (correct / 5.0) / minutes if minutes > 0 else 0.0

        self.wpm_var.set(f"WPM: {wpm:.1f}")
        self.acc_var.set(f"Accuracy: {accuracy:.1f}%")
        self.time_taken_var.set(f"Time: {elapsed:.1f}s")
        self.status_var.set("Completed" if finished else "Time up")
        self._update_status_color("stopped")

        self._log_stats_to_csv(wpm, accuracy, elapsed)

        # Stop the activity logger when the test ends (completed or time up)
        try:
            self.logger.stop_logging()
        except Exception:
            pass

        self._set_input_enabled(False)
        self._set_editable(True)

    def _log_stats_to_csv(self, wpm, accuracy, elapsed):
        filename = "typing_stats.csv"
        
        fieldnames = [
            'Timestamp', 'WPM', 'Accuracy %', 'TimeTaken', 'TestFile',
            'MouseMovementTime', 'MouseClicks', 'MouseScrolls',
            'TotalDuration', 'Backspaces'
        ]

        # Check if file needs a header
        write_header = True
        if os.path.isfile(filename):
            try:
                with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    header = next(reader)
                    if header == fieldnames:
                        write_header = False
            except (StopIteration, IOError):
                # File is empty or cannot be read, so we'll write a header
                pass
        
        test_file = self.current_test_file if self.current_test_file else "Default Text"

        try:
            # Get stats from logger
            mouse_move_time = self.logger.total_mouse_move_time
            total_clicks = self.logger.left_click_count + self.logger.right_click_count
            total_scrolls = (
                self.logger.scroll_up_count + self.logger.scroll_down_count +
                self.logger.scroll_left_count + self.logger.scroll_right_count
            )
            backspaces = self.logger.backspace_count
            
            total_duration = 0.0
            if self.logger.first_key_time and self.logger.last_key_time:
                total_duration = (self.logger.last_key_time - self.logger.first_key_time).total_seconds()

            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if write_header:
                    writer.writeheader()
                
                writer.writerow({
                    'Timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'WPM': f"{wpm:.1f}",
                    'Accuracy %': f"{accuracy:.1f}",
                    'TimeTaken': f"{elapsed:.1f}",
                    'TestFile': test_file,
                    'MouseMovementTime': f"{mouse_move_time:.3f}",
                    'MouseClicks': total_clicks,
                    'MouseScrolls': total_scrolls,
                    'TotalDuration': f"{total_duration:.3f}",
                    'Backspaces': backspaces
                })
        except Exception as e:
            messagebox.showerror("Logging Error", f"Failed to write to CSV log:\n{e}")

    def load_test(self):
        if self.test_running:
            return
        self._open_txt_picker_dialog()

    def _open_txt_picker_dialog(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        files = [f for f in os.listdir(base_dir) if f.lower().endswith(".txt")]
        files.sort(key=lambda x: x.lower())

        if not files:
            messagebox.showinfo("Load Test", "No .txt files found in this folder.")
            return

        d = tk.Toplevel(self.root)
        d.title("Select Test Text (.txt)")
        d.transient(self.root)
        d.grab_set()
        d.resizable(False, False)

        frm = ttk.Frame(d, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Choose a .txt file from this folder:").pack(anchor="w", pady=(0, 8))

        list_frame = ttk.Frame(frm)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        lb = tk.Listbox(list_frame, height=10, yscrollcommand=scrollbar.set, exportselection=False)
        scrollbar.config(command=lb.yview)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for f in files:
            lb.insert(tk.END, f)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8, 0))

        def do_open():
            sel = lb.curselection()
            if not sel:
                return
            fname = files[sel[0]]
            path = os.path.join(base_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip("\n")
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load file:\n{e}")
                return
            self.current_test_file = fname
            self.current_test_display_var.set(f"Test: {fname}")
            self.test_text = content
            self._apply_text(self.test_text)
            self.status_var.set(f"Loaded: {fname}")
            d.destroy()

        def do_cancel():
            d.destroy()

        ttk.Button(btns, text="Open", command=do_open).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(btns, text="Cancel", command=do_cancel).pack(side=tk.RIGHT)

        def on_double_click(_evt=None):
            do_open()

        def on_return(_evt=None):
            do_open()

        lb.bind("<Double-Button-1>", on_double_click)
        lb.bind("<Return>", on_return)
        lb.selection_set(0)
        lb.activate(0)
        lb.focus_set()

    def save_test(self):
        if self.test_running:
            return
        text = self.top_text.get("1.0", "end-1c")
        path = filedialog.asksaveasfilename(
            title="Save Test Text",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save file:\n{e}")
            return
        self.status_var.set(f"Saved: {path}")


def main():
    root = tk.Tk()
    app = TypingTestApp(root)
    # Open slightly larger by default, with a sensible minimum
    root.geometry("1000x700")
    root.minsize(800, 500)
    root.mainloop()


if __name__ == "__main__":
    main()
