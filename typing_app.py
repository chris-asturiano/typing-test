import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
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

        # Experiment state
        self.experiment_running = False
        self.experiment_group = None
        self.experiment_design = {
            1: {"first_kb": "60%", "second_kb": "100%", "task_order": [1, 2, 3], "content": {"60%": "A", "100%": "B"}},
            2: {"first_kb": "60%", "second_kb": "100%", "task_order": [2, 3, 1], "content": {"60%": "A", "100%": "B"}},
            3: {"first_kb": "60%", "second_kb": "100%", "task_order": [3, 1, 2], "content": {"60%": "A", "100%": "B"}},
            4: {"first_kb": "100%", "second_kb": "60%", "task_order": [1, 2, 3], "content": {"100%": "A", "60%": "B"}},
            5: {"first_kb": "100%", "second_kb": "60%", "task_order": [2, 3, 1], "content": {"100%": "A", "60%": "B"}},
            6: {"first_kb": "100%", "second_kb": "60%", "task_order": [3, 1, 2], "content": {"100%": "A", "60%": "B"}},
        }
        self.task_labels = {1: "Text Entry", 2: "Number Entry", 3: "Programming Syntax"}
        self.current_keyboard_index = 0
        self.current_task_index = 0
        self.participant_name = "" # New: Store participant's name
        self.experiment_results = {} # Stores results for the current experiment run

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
        ttk.Button(controls, text="Save Test", command=self.save_test).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Perform Experiment", command=self.perform_experiment).pack(side=tk.LEFT, padx=(0, 12))

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
        # Bind key events to logger
        self.input_text.bind("<Key>", self._on_key_for_logger, add=True)
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

    def _on_key_for_logger(self, event):
        """Pass key events to the logger"""
        try:
            self.logger.record_key_press(event.keysym)
        except:
            pass

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


    def _reset_test_state(self):
        """Resets the UI and state for a new test, without starting it."""
        try:
            self.initial_time = int(self.time_var.get())
        except Exception:
            self.initial_time = 60
            self.time_var.set(str(self.initial_time))

        text = self.top_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Typing Test", "Please provide text to type (top panel).")
            return False

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
        self.status_var.set("Ready to start")
        self._update_status_color("default")
        self.test_running = False
        self.timer_running = False

        # reset incremental-highlighting state
        self._last_typed = ""
        self._current_pos = 0
        try:
            self._retag_full("", self.test_text)
        except Exception:
            pass
        return True

    def start_test(self):
        if not self._reset_test_state():
            return
        
        self.status_var.set("Test running… Start typing!")
        self._update_status_color("pending")
        self.test_running = True
        self.timer_running = False

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
        self.wpm_var.set(f"WPM: {wpm:.1f}")
        self.acc_var.set(f"Accuracy %: {accuracy:.1f}%")
        self.time_taken_var.set(f"Time: {elapsed:.1f}s")
        self.status_var.set("Stopped")
        self._update_status_color("stopped")

        # Get stats from logger for single test logging
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

        self._log_single_test_stats_to_separate_csv(wpm, accuracy, elapsed, mouse_move_time, total_clicks, total_scrolls, backspaces)
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
        error_rate = (100.0 - accuracy) if total_typed > 0 else 0.0

        minutes = max(elapsed, 1e-9) / 60.0
        wpm = (correct / 5.0) / minutes if minutes > 0 else 0.0

        self.wpm_var.set(f"WPM: {wpm:.1f}")
        self.acc_var.set(f"Accuracy: {accuracy:.1f}%")
        self.time_taken_var.set(f"Time: {elapsed:.1f}s")
        self.status_var.set("Completed" if finished else "Time up")
        self._update_status_color("stopped")

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

        if self.experiment_running:
            group_config = self.experiment_design[self.experiment_group]
            current_keyboard = group_config["first_kb"] if self.current_keyboard_index == 0 else group_config["second_kb"]
            current_task_id = group_config["task_order"][self.current_task_index]
            task_name_prefix = self.task_labels[current_task_id].split(" ")[0] # e.g., "Text", "Number", "Programming"
            
            # Map task names to CSV prefixes
            task_prefix_map = {
                "Text": "Text",
                "Number": "Num",
                "Programming": "Prog"
            }
            csv_task_prefix = task_prefix_map.get(task_name_prefix, task_name_prefix)

            # Store results for the current task
            key_prefix = f"{csv_task_prefix}_{current_keyboard.replace('%', '')}"
            self.experiment_results[f"{key_prefix}_WPM"] = f"{wpm:.1f}"
            self.experiment_results[f"{key_prefix}_Accuracy"] = f"{accuracy:.1f}"
            self.experiment_results[f"{key_prefix}_ErrorRate"] = f"{error_rate:.1f}"
            self.experiment_results[f"{key_prefix}_MouseTime"] = f"{mouse_move_time:.3f}"
            self.experiment_results[f"{key_prefix}_Clicks"] = total_clicks
            self.experiment_results[f"{key_prefix}_Backspaces"] = backspaces
            self.experiment_results[f"{key_prefix}_Scrolls"] = total_scrolls
            self.experiment_results[f"{key_prefix}_TotalTime"] = f"{elapsed:.3f}"
        else:
            self._log_single_test_stats_to_separate_csv(wpm, accuracy, elapsed, mouse_move_time, total_clicks, total_scrolls, backspaces)

        # Stop the activity logger when the test ends (completed or time up)
        try:
            self.logger.stop_logging()
        except Exception:
            pass

        self._set_input_enabled(False)
        self._set_editable(True)

        if self.experiment_running:
            self.root.after(100, self._handle_experiment_continuation)

    def _log_single_test_stats_to_separate_csv(self, wpm, accuracy, elapsed, mouse_move_time, total_clicks, total_scrolls, backspaces):
        filename = "single_typing_stats.csv"
        
        fieldnames = [
            'Timestamp', 'Participant', 'GroupNumber', 'WPM', 'Accuracy %', 'TimeTaken', 'TestFile',
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
                    'Participant': self.participant_name if self.participant_name else "Default", 
                    'GroupNumber': self.experiment_group if self.experiment_group else "N/A", 
                    'WPM': f"{wpm:.1f}",
                    'Accuracy %': f"{accuracy:.1f}",
                    'TimeTaken': f"{elapsed:.1f}",
                    'TestFile': test_file,
                    'MouseMovementTime': f"{mouse_move_time:.3f}",
                    'MouseClicks': total_clicks,
                    'MouseScrolls': total_scrolls,
                    'TotalDuration': f"{elapsed:.3f}",
                    'Backspaces': backspaces
                })
        except Exception as e:
            messagebox.showerror("Logging Error", f"Failed to write to CSV log:\n{e}")

    def _save_experiment_results_to_csv(self):
        filename = "typing_stats.csv"
        
        # Define fieldnames based on the dummy CSV, excluding 'Task_Variant'
        fieldnames = [
            'Participant', 'GroupNumber',
            'Text_60_WPM', 'Text_60_Accuracy', 'Text_60_ErrorRate', 'Text_60_MouseTime', 'Text_60_Clicks', 'Text_60_Backspaces', 'Text_60_Scrolls', 'Text_60_TotalTime',
            'Num_60_WPM', 'Num_60_Accuracy', 'Num_60_ErrorRate', 'Num_60_MouseTime', 'Num_60_Clicks', 'Num_60_Backspaces', 'Num_60_Scrolls', 'Num_60_TotalTime',
            'Prog_60_WPM', 'Prog_60_Accuracy', 'Prog_60_ErrorRate', 'Prog_60_MouseTime', 'Prog_60_Clicks', 'Prog_60_Backspaces', 'Prog_60_Scrolls', 'Prog_60_TotalTime',
            'Text_100_WPM', 'Text_100_Accuracy', 'Text_100_ErrorRate', 'Text_100_MouseTime', 'Text_100_Clicks', 'Text_100_Backspaces', 'Text_100_Scrolls', 'Text_100_TotalTime',
            'Num_100_WPM', 'Num_100_Accuracy', 'Num_100_ErrorRate', 'Num_100_MouseTime', 'Num_100_Clicks', 'Num_100_Backspaces', 'Num_100_Scrolls', 'Num_100_TotalTime',
            'Prog_100_WPM', 'Prog_100_Accuracy', 'Prog_100_ErrorRate', 'Prog_100_MouseTime', 'Prog_100_Clicks', 'Prog_100_Backspaces', 'Prog_100_Scrolls', 'Prog_100_TotalTime'
        ]

        write_header = True
        if os.path.isfile(filename):
            try:
                with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    header = next(reader)
                    if header == fieldnames:
                        write_header = False
            except (StopIteration, IOError):
                pass # File is empty or cannot be read, so we'll write a header

        try:
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if write_header:
                    writer.writeheader()
                
                row_data = {field: '' for field in fieldnames} # Initialize all fields to empty strings
                row_data['Participant'] = self.participant_name
                row_data['GroupNumber'] = self.experiment_group
                row_data.update(self.experiment_results) # Update with actual results

                writer.writerow(row_data)
            messagebox.showinfo("Experiment Log", "Experiment results saved to typing_stats.csv")
        except Exception as e:
            messagebox.showerror("Logging Error", f"Failed to write experiment results to CSV log:\n{e}")
        finally:
            self.experiment_results = {} # Clear results after saving

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

    def _handle_experiment_continuation(self):
        group_config = self.experiment_design[self.experiment_group]
        task_order = group_config["task_order"]
        
        current_task_id = task_order[self.current_task_index]
        task_name = self.task_labels[current_task_id]

        self.current_task_index += 1

        if self.current_task_index < len(task_order):
            next_task_id = task_order[self.current_task_index]
            next_task_name = self.task_labels[next_task_id]
            if messagebox.askyesno("Task Complete", f"{task_name} Test Done.\nMove onto {next_task_name} task?"):
                self._advance_experiment()
            else:
                self.experiment_running = False
        else:
            # This was the last task for the current keyboard
            self._advance_experiment()

    def perform_experiment(self):
        if self.test_running:
            messagebox.showwarning("Experiment", "A test is already running. Please stop it before starting an experiment.")
            return

        # Simple dialog to get group number
        group = tk.simpledialog.askinteger("Experiment Setup", "Enter Group Number (1-6):", parent=self.root, minvalue=1, maxvalue=6)
        if group is None:
            return

        participant_name = tk.simpledialog.askstring("Experiment Setup", "Enter Participant Name:", parent=self.root)
        if participant_name is None or not participant_name.strip():
            messagebox.showwarning("Experiment Setup", "Participant name cannot be empty.")
            return
        self.participant_name = participant_name.strip()

        self.experiment_group = group
        self._start_experiment_flow(group)

    def _start_experiment_flow(self, group_id: int):
        self.experiment_running = True
        self.experiment_group = group_id
        self.current_keyboard_index = 0
        self.current_task_index = 0
        self.experiment_results = {} # Clear results for a new experiment
        self._advance_experiment()

    def _advance_experiment(self):
        if not self.experiment_running:
            return

        group_config = self.experiment_design[self.experiment_group]
        keyboards = [group_config["first_kb"], group_config["second_kb"]]
        task_order = group_config["task_order"]

        if self.current_keyboard_index >= len(keyboards):
            messagebox.showinfo("Experiment Complete", f"All tasks for Group {self.experiment_group} are done.")
            self._save_experiment_results_to_csv() # Save results when experiment is complete
            self.experiment_running = False
            return

        current_keyboard = keyboards[self.current_keyboard_index]

        if self.current_task_index >= len(task_order):
            self.current_keyboard_index += 1
            self.current_task_index = 0
            if self.current_keyboard_index >= len(keyboards):
                messagebox.showinfo("Experiment Complete", f"All tasks for Group {self.experiment_group} are done.")
                self._save_experiment_results_to_csv() # Save results when experiment is complete
                self.experiment_running = False
                return
            
            next_keyboard = keyboards[self.current_keyboard_index]
            if messagebox.askyesno("Next Keyboard", f"First keyboard tasks complete. Switch to the {next_keyboard} keyboard and continue?"):
                self._advance_experiment()
            else:
                self.experiment_running = False
            return

        current_task_id = task_order[self.current_task_index]
        task_name = self.task_labels[current_task_id]
        content_version = group_config["content"][current_keyboard]

        self._load_experiment_test_file(task_name, content_version)
        self._reset_test_state()
        self._set_input_enabled(False) # Disable until they click start

        message = (
            f"Assigned Keyboard: {current_keyboard}\n"
            f"Starting Task: {task_name} (Version {content_version})\n\n"
            f"Click 'Start Test' to begin."
        )
        messagebox.showinfo("Next Task", message)
        # Re-enable after popup
        self.root.after(100, lambda: self._set_input_enabled(True))

    def _load_experiment_test_file(self, task_name: str, version: str):
        # Maps task names to file prefixes
        task_to_prefix = {
            "Text Entry": "Text",
            "Number Entry": "Number",
            "Programming Syntax": "Programming"
        }
        prefix = task_to_prefix.get(task_name)
        if not prefix:
            messagebox.showerror("Error", f"Unknown task name: {task_name}")
            return

        fname = f"{prefix}{version}.txt"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, fname)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip("\n")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load file: {fname}\n{e}")
            self.experiment_running = False
            return

        self.current_test_file = fname
        self.current_test_display_var.set(f"Test: {fname}")
        self.test_text = content
        self._apply_text(self.test_text)
        self.status_var.set(f"Loaded: {fname}")


def main():
    root = tk.Tk()
    app = TypingTestApp(root)
    # Open slightly larger by default, with a sensible minimum
    root.geometry("1000x700")
    root.minsize(800, 500)
    root.mainloop()


if __name__ == "__main__":
    main()
