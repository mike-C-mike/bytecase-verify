import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from compare_core import (
    build_compare_report,
    load_manifest_json as load_compare_manifest_json,
    save_compare_outputs
)
from hash_core import (
    build_manifest,
    collect_files,
    get_total_size_bytes,
    hash_files,
    save_manifest_outputs
)
from settings_service import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DEFAULT_ROOT_FOLDER_NAME,
    PRODUCT_DOMAIN,
    PUBLISHER_NAME,
    SUITE_NAME,
    TOOL_FOLDER_NAME,
    ensure_directories,
    format_export_path_list,
    get_default_output_root,
    load_or_create_settings,
    save_settings
)
from bytecase_theme import (
    THEME_DISPLAY_NAMES,
    apply_theme as apply_bytecase_theme,
    configure_toplevel,
    display_theme_preference,
    style_text_widget as style_bytecase_text_widget,
    theme_preference_from_display,
)
from validators import (
    format_bytes,
    summarize_hash_results,
    validate_hash_request,
    validate_manifest_for_export
)
from verification_core import (
    build_verification_report,
    get_manifest_algorithms,
    load_manifest_json,
    save_verification_outputs
)


class HashManifestApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} - {APP_SUBTITLE} v{APP_VERSION}")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.settings = load_or_create_settings()

        self.selected_files = []
        self.selected_folders = []
        self.hash_results = []

        self.verification_manifest = None
        self.verification_manifest_path = ""

        self.total_bytes = 0
        self.processed_bytes = 0
        self.hashing_active = False

        self.progress_queue = queue.Queue()
        self.theme_colors = {}

        self.apply_theme()
        self.build_gui()
        self.load_defaults_from_settings()
        self.poll_progress_queue()

    def on_close(self):
        if self.hashing_active:
            confirm = messagebox.askyesno(
                "Hashing In Progress",
                "Hashing is currently in progress. Closing the application will stop the operation.\n\n"
                "Are you sure you want to close?"
            )

            if not confirm:
                return

        self.root.destroy()

    def apply_theme(self):
        self.theme_state = apply_bytecase_theme(self.root, self.settings)
        self.theme_colors = self.theme_state["colors"]

    def refresh_classic_widget_themes(self, widget=None):
        if widget is None:
            widget = self.root

        colors = getattr(self, "theme_colors", {})
        if not colors:
            return

        try:
            if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Canvas)):
                widget.configure(bg=colors["app_background"])
            elif isinstance(widget, tk.Text):
                self.style_text_widget(widget)
        except tk.TclError:
            pass

        try:
            for child in widget.winfo_children():
                self.refresh_classic_widget_themes(child)
        except tk.TclError:
            pass

    def style_text_widget(self, widget):
        colors = getattr(self, "theme_colors", None)

        if not colors:
            return

        style_bytecase_text_widget(widget, colors)

    def build_gui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(0, weight=1)

        ttk.Label(top_frame, text=f"{APP_NAME} v{APP_VERSION}", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            top_frame,
            text=f"{APP_SUBTITLE} | Part of {SUITE_NAME} by {PUBLISHER_NAME}",
            style="Subtitle.TLabel"
        ).grid(row=1, column=0, sticky="w")

        button_frame = ttk.Frame(top_frame)
        button_frame.grid(row=0, column=1, sticky="e")

        ttk.Button(button_frame, text="Settings", command=self.open_settings_window).grid(row=0, column=0, padx=4)
        ttk.Button(button_frame, text="About", command=self.open_about_window).grid(row=0, column=1, padx=4)
        ttk.Button(button_frame, text="Open Output Folder", command=self.open_output_folder).grid(row=0, column=2, padx=4)

        main_wrapper = ttk.Frame(self.root)
        main_wrapper.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_wrapper.columnconfigure(0, weight=1)
        main_wrapper.rowconfigure(0, weight=1)

        colors = getattr(self, "theme_colors", {})
        self.main_canvas = tk.Canvas(
            main_wrapper,
            highlightthickness=0,
            borderwidth=0,
            background=colors.get("app_background", "#0E1116")
        )
        self.main_canvas.grid(row=0, column=0, sticky="nsew")

        main_y_scroll = ttk.Scrollbar(main_wrapper, orient="vertical", command=self.main_canvas.yview)
        main_y_scroll.grid(row=0, column=1, sticky="ns")

        main_x_scroll = ttk.Scrollbar(main_wrapper, orient="horizontal", command=self.main_canvas.xview)
        main_x_scroll.grid(row=1, column=0, sticky="ew")

        self.main_canvas.configure(
            yscrollcommand=main_y_scroll.set,
            xscrollcommand=main_x_scroll.set
        )

        self.main_content = ttk.Frame(self.main_canvas)
        self.main_content_window = self.main_canvas.create_window(
            (0, 0),
            window=self.main_content,
            anchor="nw"
        )

        self.main_content.columnconfigure(0, weight=1)
        self.main_content.rowconfigure(1, weight=1)

        self.main_content.bind("<Configure>", self.update_main_scroll_region)
        self.main_canvas.bind("<Configure>", self.resize_main_canvas_window)
        self.main_canvas.bind("<Enter>", self.bind_main_mousewheel)
        self.main_canvas.bind("<Leave>", self.unbind_main_mousewheel)

        upper_frame = ttk.Frame(self.main_content)
        upper_frame.grid(row=0, column=0, sticky="ew")
        upper_frame.columnconfigure(0, weight=1)
        upper_frame.columnconfigure(1, weight=1)

        lower_frame = ttk.Frame(self.main_content)
        lower_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        lower_frame.columnconfigure(0, weight=1)
        lower_frame.rowconfigure(0, weight=1)

        self.build_input_section(upper_frame)
        self.build_results_section(lower_frame)

    def update_main_scroll_region(self, event=None):
        if hasattr(self, "main_canvas"):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def resize_main_canvas_window(self, event):
        if hasattr(self, "main_canvas") and hasattr(self, "main_content_window"):
            self.main_canvas.itemconfigure(self.main_content_window, width=max(event.width, 1100))

    def bind_main_mousewheel(self, event=None):
        self.root.bind_all("<MouseWheel>", self.on_main_mousewheel)
        self.root.bind_all("<Shift-MouseWheel>", self.on_main_shift_mousewheel)

    def unbind_main_mousewheel(self, event=None):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Shift-MouseWheel>")

    def on_main_mousewheel(self, event):
        if hasattr(self, "main_canvas"):
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_main_shift_mousewheel(self, event):
        if hasattr(self, "main_canvas"):
            self.main_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def build_input_section(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        case_frame = ttk.LabelFrame(parent, text="Manifest Information", padding=10)
        case_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        case_frame.columnconfigure(1, weight=1)

        self.case_number_var = tk.StringVar()
        self.agency_case_number_var = tk.StringVar()
        self.exhibit_reference_var = tk.StringVar()
        self.technician_var = tk.StringVar()
        self.reviewed_by_var = tk.StringVar()
        self.source_description_var = tk.StringVar()

        self.add_labeled_entry(case_frame, "Case Number", self.case_number_var, 0)
        self.add_labeled_entry(case_frame, "Agency Case Number", self.agency_case_number_var, 1)
        self.add_labeled_entry(case_frame, "Exhibit / Item Reference", self.exhibit_reference_var, 2)
        self.add_labeled_technician_combo(case_frame, "Technician", self.technician_var, 3)
        self.add_labeled_entry(case_frame, "Reviewed By", self.reviewed_by_var, 4)
        self.add_labeled_entry(case_frame, "Source Description", self.source_description_var, 5)

        ttk.Label(case_frame, text="Manifest / Verification / Compare Notes").grid(row=6, column=0, sticky="nw", pady=4)
        self.notes_text = tk.Text(case_frame, height=4, width=50)
        self.notes_text.grid(row=6, column=1, sticky="ew", pady=4)
        self.style_text_widget(self.notes_text)

        options_frame = ttk.LabelFrame(parent, text="Hash / Report Options", padding=10)
        options_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        options_frame.columnconfigure(0, weight=1)

        self.md5_var = tk.BooleanVar(value=True)
        self.sha1_var = tk.BooleanVar(value=False)
        self.sha256_var = tk.BooleanVar(value=True)
        self.recursive_var = tk.BooleanVar(value=True)
        self.include_explanation_var = tk.BooleanVar(value=True)
        self.include_generation_method_var = tk.BooleanVar(value=True)
        self.include_signature_block_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="MD5", variable=self.md5_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="SHA-1", variable=self.sha1_var).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="SHA-256", variable=self.sha256_var).grid(row=2, column=0, sticky="w")

        ttk.Separator(options_frame).grid(row=3, column=0, sticky="ew", pady=8)

        ttk.Checkbutton(options_frame, text="Include folders recursively", variable=self.recursive_var).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="Include hash generation method in TXT report", variable=self.include_generation_method_var).grid(row=5, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="Include hashing explanation in TXT report", variable=self.include_explanation_var).grid(row=6, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="Include report signature block", variable=self.include_signature_block_var).grid(row=7, column=0, sticky="w")

        selection_frame = ttk.LabelFrame(parent, text="File / Folder Selection", padding=10)
        selection_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        selection_frame.columnconfigure(0, weight=1)

        selection_buttons = ttk.Frame(selection_frame)
        selection_buttons.grid(row=0, column=0, sticky="w")

        ttk.Button(selection_buttons, text="Add Files", command=self.add_files).grid(row=0, column=0, padx=4)
        ttk.Button(selection_buttons, text="Add Folder", command=self.add_folder).grid(row=0, column=1, padx=4)
        ttk.Button(selection_buttons, text="View Selected Items", command=self.view_selected_items).grid(row=0, column=2, padx=4)
        ttk.Button(selection_buttons, text="Clear Selection", command=self.clear_selection).grid(row=0, column=3, padx=4)

        self.selection_summary_var = tk.StringVar(value="No files or folders selected.")
        ttk.Label(selection_frame, textvariable=self.selection_summary_var, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))

        action_frame = ttk.Frame(selection_frame)
        action_frame.grid(row=0, column=1, sticky="e")

        self.hash_button = ttk.Button(action_frame, text="Hash Selected Items", command=self.start_hashing)
        self.hash_button.grid(row=0, column=0, padx=4)

        self.review_button = ttk.Button(action_frame, text="Review Manifest", command=self.review_manifest, state="disabled")
        self.review_button.grid(row=0, column=1, padx=4)

        self.review_verification_button = ttk.Button(action_frame, text="Review Verification", command=self.review_verification, state="disabled")
        self.review_verification_button.grid(row=0, column=2, padx=4)

        ttk.Button(action_frame, text="Clear Manifest", command=self.clear_manifest).grid(row=0, column=3, padx=4)

        utilities_frame = ttk.LabelFrame(parent, text="Manifest Utilities", padding=10)
        utilities_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        utilities_frame.columnconfigure(1, weight=1)

        ttk.Button(utilities_frame, text="Load Prior Manifest JSON", command=self.load_prior_manifest).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Button(utilities_frame, text="Clear Prior Manifest", command=self.clear_prior_manifest).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Button(utilities_frame, text="Compare Two Manifests", command=self.open_compare_window).grid(row=0, column=2, sticky="e", padx=4)

        self.verification_manifest_var = tk.StringVar(value="No prior manifest loaded.")
        ttk.Label(utilities_frame, textvariable=self.verification_manifest_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style="Horizontal.TProgressbar").grid(row=0, column=0, sticky="ew")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.current_file_var = tk.StringVar(value="")
        ttk.Label(progress_frame, textvariable=self.current_file_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w")

    def build_results_section(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        results_frame = ttk.LabelFrame(parent, text="Hash Results", padding=10)
        results_frame.grid(row=0, column=0, sticky="nsew")
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        columns = ("file_name", "size", "status", "md5", "sha1", "sha256", "path")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)

        headings = {
            "file_name": "File Name",
            "size": "Size",
            "status": "Status",
            "md5": "MD5",
            "sha1": "SHA-1",
            "sha256": "SHA-256",
            "path": "Path"
        }

        widths = {
            "file_name": 180,
            "size": 90,
            "status": 90,
            "md5": 220,
            "sha1": 220,
            "sha256": 320,
            "path": 420
        }

        for column in columns:
            self.results_tree.heading(column, text=headings[column])
            self.results_tree.column(column, width=widths[column], anchor="w")

        y_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        x_scroll = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results_tree.xview)

        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def add_labeled_entry(self, parent, label_text, variable, row):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)

    def add_labeled_technician_combo(self, parent, label_text, variable, row):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=4)

        self.technician_combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=self.get_technician_values(),
            state="normal"
        )
        self.technician_combo.grid(row=row, column=1, sticky="ew", pady=4)

    def get_technician_values(self):
        technicians = self.settings.get("technicians", [])

        if not isinstance(technicians, list):
            return []

        cleaned = []
        seen = set()

        for technician in technicians:
            technician = str(technician).strip()

            if not technician:
                continue

            key = technician.lower()

            if key not in seen:
                cleaned.append(technician)
                seen.add(key)

        return cleaned

    def refresh_technician_dropdown(self):
        if hasattr(self, "technician_combo"):
            self.technician_combo["values"] = self.get_technician_values()

    def load_defaults_from_settings(self):
        self.refresh_technician_dropdown()
        self.technician_var.set(self.settings.get("default_technician", ""))

        hash_defaults = self.settings.get("hash_defaults", {})
        report_defaults = self.settings.get("report_defaults", {})

        self.md5_var.set(bool(hash_defaults.get("md5", True)))
        self.sha1_var.set(bool(hash_defaults.get("sha1", False)))
        self.sha256_var.set(bool(hash_defaults.get("sha256", True)))
        self.include_explanation_var.set(bool(hash_defaults.get("include_hashing_explanation", True)))
        self.include_generation_method_var.set(bool(hash_defaults.get("include_hash_generation_method", True)))
        self.include_signature_block_var.set(bool(report_defaults.get("include_signature_block", True)))

    def get_selected_algorithms(self):
        return {
            "md5": self.md5_var.get(),
            "sha1": self.sha1_var.get(),
            "sha256": self.sha256_var.get()
        }

    def add_files(self):
        file_paths = filedialog.askopenfilenames(title="Select Files to Hash")

        if not file_paths:
            return

        for file_path in file_paths:
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)

        self.update_selection_summary()

    def add_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder to Hash")

        if not folder_path:
            return

        if folder_path not in self.selected_folders:
            self.selected_folders.append(folder_path)

        self.update_selection_summary()

    def load_prior_manifest(self):
        path = filedialog.askopenfilename(
            title="Select Prior Manifest JSON",
            filetypes=[
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )

        if not path:
            return

        try:
            manifest = load_manifest_json(path)
        except Exception as e:
            messagebox.showerror("Load Manifest Error", f"Could not load prior manifest.\n\nDetails:\n{e}")
            return

        self.verification_manifest = manifest
        self.verification_manifest_path = path

        case_info = manifest.get("case_info", {})
        case_number = case_info.get("case_number", "")
        source_description = case_info.get("source_description", "")

        label = f"Loaded prior manifest: {path}"

        if case_number or source_description:
            label += f" | Case: {case_number} | Source: {source_description}"

        self.verification_manifest_var.set(label)

        algorithms = get_manifest_algorithms(manifest)

        if algorithms:
            self.md5_var.set("MD5" in algorithms)
            self.sha1_var.set("SHA-1" in algorithms)
            self.sha256_var.set("SHA-256" in algorithms)

        if self.hash_results:
            self.review_verification_button.config(state="normal")

        messagebox.showinfo(
            "Prior Manifest Loaded",
            "Prior manifest loaded successfully.\n\n"
            "Hash the current files/folders, then click Review Verification."
        )

    def clear_prior_manifest(self):
        self.verification_manifest = None
        self.verification_manifest_path = ""
        self.verification_manifest_var.set("No prior manifest loaded.")
        self.review_verification_button.config(state="disabled")

    def open_compare_window(self):
        CompareWindow(self)

    def view_selected_items(self):
        if not self.selected_files and not self.selected_folders:
            messagebox.showinfo("Selected Items", "No files or folders selected.")
            return

        window = tk.Toplevel(self.root)
        window.title("Selected Items")
        window.geometry("850x500")
        window.transient(self.root)

        colors = getattr(self, "theme_colors", {})
        if colors:
            window.configure(bg=colors["app_background"])

        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)

        text_box = tk.Text(frame, wrap="none")
        text_box.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text_box.yview)
        y_scroll.pack(side="right", fill="y")
        text_box.configure(yscrollcommand=y_scroll.set)

        self.style_text_widget(text_box)

        text_box.insert("end", "FILES\n")
        text_box.insert("end", "-" * 80 + "\n")

        if self.selected_files:
            for path in self.selected_files:
                text_box.insert("end", f"{path}\n")
        else:
            text_box.insert("end", "No individual files selected.\n")

        text_box.insert("end", "\nFOLDERS\n")
        text_box.insert("end", "-" * 80 + "\n")

        if self.selected_folders:
            for path in self.selected_folders:
                text_box.insert("end", f"{path}\n")
        else:
            text_box.insert("end", "No folders selected.\n")

        text_box.configure(state="disabled")

    def clear_selection(self):
        if self.hashing_active:
            messagebox.showwarning("Hashing Active", "Cannot clear selection while hashing is in progress.")
            return

        self.selected_files = []
        self.selected_folders = []
        self.update_selection_summary()

    def update_selection_summary(self):
        self.selection_summary_var.set(
            f"Selected files: {len(self.selected_files)} | Selected folders: {len(self.selected_folders)}"
        )

    def start_hashing(self):
        if self.hashing_active:
            return

        algorithms = self.get_selected_algorithms()
        errors, warnings = validate_hash_request(self.selected_files, self.selected_folders, algorithms)

        if errors:
            messagebox.showerror("Hashing Validation Error", "Fix the following before hashing:\n\n" + "\n".join(errors))
            return

        files = collect_files(
            selected_files=self.selected_files,
            selected_folders=self.selected_folders,
            recursive=self.recursive_var.get()
        )

        if not files:
            messagebox.showerror("No Files Found", "No hashable files were found in the selected items.")
            return

        self.hash_results = []
        self.clear_results_table()

        self.total_bytes = get_total_size_bytes(files)
        self.processed_bytes = 0
        self.progress_var.set(0)

        self.hashing_active = True
        self.hash_button.config(state="disabled")
        self.review_button.config(state="disabled")
        self.review_verification_button.config(state="disabled")

        self.status_var.set(f"Hashing 0 of {len(files)} files...")
        self.current_file_var.set("Preparing...")

        worker = threading.Thread(target=self.hashing_worker, args=(files, algorithms), daemon=True)
        worker.start()

    def hashing_worker(self, files, algorithms):
        try:
            def status_callback(status):
                self.progress_queue.put(("status", status))

            def progress_callback(bytes_processed):
                self.progress_queue.put(("progress", bytes_processed))

            results = hash_files(
                files,
                algorithms,
                status_callback=status_callback,
                progress_callback=progress_callback
            )

            self.progress_queue.put(("complete", results))

        except Exception as e:
            self.progress_queue.put(("error", str(e)))

    def poll_progress_queue(self):
        try:
            while True:
                message_type, payload = self.progress_queue.get_nowait()

                if message_type == "status":
                    self.status_var.set(f"Hashing file {payload.get('current_index', 0)} of {payload.get('total_files', 0)}")
                    self.current_file_var.set(f"Current file: {payload.get('current_file', '')}")

                elif message_type == "progress":
                    self.processed_bytes += payload

                    if self.total_bytes > 0:
                        percent = min((self.processed_bytes / self.total_bytes) * 100, 100)
                    else:
                        percent = 0

                    self.progress_var.set(percent)

                elif message_type == "complete":
                    self.hash_results = payload
                    self.progress_var.set(100)
                    self.status_var.set(f"Hashing complete. Files processed: {len(self.hash_results)}")
                    self.current_file_var.set("")
                    self.populate_results_table()
                    self.hashing_active = False
                    self.hash_button.config(state="normal")
                    self.review_button.config(state="normal")

                    if self.verification_manifest:
                        self.review_verification_button.config(state="normal")

                    messagebox.showinfo("Hashing Complete", "Hash results are ready to review.")

                elif message_type == "error":
                    self.hashing_active = False
                    self.hash_button.config(state="normal")
                    self.review_button.config(state="disabled")
                    self.review_verification_button.config(state="disabled")
                    self.status_var.set("Hashing failed.")
                    self.current_file_var.set("")
                    messagebox.showerror("Hashing Error", payload)

        except queue.Empty:
            pass

        self.root.after(100, self.poll_progress_queue)

    def populate_results_table(self):
        self.clear_results_table()

        for record in self.hash_results:
            self.results_tree.insert(
                "",
                "end",
                values=(
                    record.get("file_name", ""),
                    format_bytes(record.get("file_size_bytes")),
                    record.get("hash_status", ""),
                    record.get("md5") or "Not calculated",
                    record.get("sha1") or "Not calculated",
                    record.get("sha256") or "Not calculated",
                    record.get("file_path", "")
                )
            )

    def clear_results_table(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

    def build_manifest_from_form(self):
        notes = self.notes_text.get("1.0", "end").strip()

        return build_manifest(
            settings=self.settings,
            case_number=self.case_number_var.get(),
            agency_case_number=self.agency_case_number_var.get(),
            technician=self.technician_var.get(),
            reviewed_by=self.reviewed_by_var.get(),
            source_description=self.source_description_var.get(),
            exhibit_reference=self.exhibit_reference_var.get(),
            recursive=self.recursive_var.get(),
            algorithms=self.get_selected_algorithms(),
            include_hashing_explanation=self.include_explanation_var.get(),
            include_hash_generation_method=self.include_generation_method_var.get(),
            include_signature_block=self.include_signature_block_var.get(),
            notes=notes,
            files=self.hash_results
        )

    def build_review_text(self, manifest, warnings):
        case_info = manifest.get("case_info", {})
        hash_settings = manifest.get("hash_settings", {})
        report_options = manifest.get("report_options", {})
        files = manifest.get("files", [])
        summary = summarize_hash_results(files)

        lines = []
        lines.append("HASH MANIFEST REVIEW")
        lines.append("=" * 80)
        lines.append("")
        lines.append("CASE INFORMATION")
        lines.append("-" * 80)
        lines.append(f"Case Number: {case_info.get('case_number', '')}")
        lines.append(f"Agency Case Number: {case_info.get('agency_case_number', '')}")
        lines.append(f"Exhibit / Item Reference: {case_info.get('exhibit_reference', '')}")
        lines.append(f"Technician: {case_info.get('technician', '')}")
        lines.append(f"Reviewed By: {case_info.get('reviewed_by', '')}")
        lines.append(f"Source Description: {case_info.get('source_description', '')}")
        lines.append("")
        lines.append("HASH / REPORT SETTINGS")
        lines.append("-" * 80)
        algorithms = hash_settings.get("algorithms", [])
        lines.append(f"Algorithms: {', '.join(algorithms) if algorithms else 'None'}")
        lines.append(f"Recursive Folder Selection: {'Yes' if hash_settings.get('recursive') else 'No'}")
        lines.append(f"Include Signature Block: {'Yes' if report_options.get('include_signature_block') else 'No'}")
        lines.append("")
        lines.append("FILE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Files: {summary['total_files']}")
        lines.append(f"Completed: {summary['completed_count']}")
        lines.append(f"Errors: {summary['error_count']}")
        lines.append(f"Total Size: {format_bytes(summary['total_size_bytes'])}")
        lines.append("")

        if warnings:
            lines.append("WARNINGS")
            lines.append("-" * 80)

            for warning in warnings:
                lines.append(f"- {warning}")

            lines.append("")

        lines.append("This review has not written any output files yet.")
        lines.append("Click Confirm Export to write the selected export formats. JSON is always created.")

        return "\n".join(lines)

    def review_manifest(self):
        if self.hashing_active:
            messagebox.showwarning("Hashing Active", "Wait for hashing to finish before reviewing.")
            return

        if not self.hash_results:
            messagebox.showerror("No Hash Results", "Hash files before reviewing a manifest.")
            return

        manifest = self.build_manifest_from_form()
        errors, warnings = validate_manifest_for_export(manifest)

        if errors:
            messagebox.showerror("Manifest Validation Error", "Fix the following before export:\n\n" + "\n".join(errors))
            return

        ReviewWindow(self, manifest, warnings)

    def review_verification(self):
        if self.hashing_active:
            messagebox.showwarning("Hashing Active", "Wait for hashing to finish before reviewing verification.")
            return

        if not self.verification_manifest:
            messagebox.showerror("No Prior Manifest", "Load a prior manifest JSON before reviewing verification.")
            return

        if not self.hash_results:
            messagebox.showerror("No Current Hash Results", "Hash current files before reviewing verification.")
            return

        notes = self.notes_text.get("1.0", "end").strip()

        report = build_verification_report(
            original_manifest=self.verification_manifest,
            current_files=self.hash_results,
            technician=self.technician_var.get(),
            notes=notes
        )

        VerificationReviewWindow(self, report)

    def export_reviewed_manifest(self, manifest, review_window):
        try:
            outputs = save_manifest_outputs(manifest, self.settings)

            review_window.destroy()
            self.status_var.set("Manifest exported successfully.")

            messagebox.showinfo(
                "Manifest Exported",
                "Hash manifest exported successfully.\n\n"
                + format_export_path_list(outputs)
            )

        except Exception as e:
            messagebox.showerror(
                "Export Error",
                f"The manifest could not be exported.\n\nDetails:\n{e}"
            )

    def export_verification_report(self, report, review_window):
        try:
            outputs = save_verification_outputs(report, self.settings)

            review_window.destroy()
            self.status_var.set("Verification report exported successfully.")

            messagebox.showinfo(
                "Verification Exported",
                "Verification report exported successfully.\n\n"
                + format_export_path_list(outputs)
            )

        except Exception as e:
            messagebox.showerror("Verification Export Error", f"The verification report could not be exported.\n\nDetails:\n{e}")

    def export_compare_report(self, report, review_window):
        try:
            outputs = save_compare_outputs(report, self.settings)

            review_window.destroy()
            self.status_var.set("Compare report exported successfully.")

            messagebox.showinfo(
                "Compare Exported",
                "Compare report exported successfully.\n\n"
                + format_export_path_list(outputs)
            )

        except Exception as e:
            messagebox.showerror("Compare Export Error", f"The compare report could not be exported.\n\nDetails:\n{e}")

    def clear_manifest(self):
        if self.hashing_active:
            messagebox.showwarning("Hashing Active", "Cannot clear while hashing is in progress.")
            return

        self.selected_files = []
        self.selected_folders = []
        self.hash_results = []
        self.total_bytes = 0
        self.processed_bytes = 0

        self.case_number_var.set("")
        self.agency_case_number_var.set("")
        self.exhibit_reference_var.set("")
        self.technician_var.set(self.settings.get("default_technician", ""))
        self.reviewed_by_var.set("")
        self.source_description_var.set("")
        self.notes_text.delete("1.0", "end")
        self.include_signature_block_var.set(
            bool(self.settings.get("report_defaults", {}).get("include_signature_block", True))
        )

        self.progress_var.set(0)
        self.status_var.set("Ready.")
        self.current_file_var.set("")
        self.review_button.config(state="disabled")
        self.review_verification_button.config(state="disabled")

        self.clear_results_table()
        self.update_selection_summary()

    def open_output_folder(self):
        case_number = self.case_number_var.get().strip() if hasattr(self, "case_number_var") else ""

        if case_number:
            paths = ensure_directories(self.settings, case_number=case_number)
            output_dir = paths["tool_dir"]
        else:
            paths = ensure_directories(self.settings, case_number="NO_CASE")
            output_dir = paths["root_dir"]

        try:
            os.startfile(output_dir)
        except OSError as e:
            messagebox.showerror("Open Output Folder Error", str(e))

    def open_about_window(self):
        AboutWindow(self)

    def open_settings_window(self):
        SettingsWindow(self)

    def refresh_after_settings_save(self):
        self.settings = load_or_create_settings()
        self.apply_theme()
        self.refresh_classic_widget_themes()
        self.load_defaults_from_settings()


class ReviewWindow:
    def __init__(self, app, manifest, warnings):
        self.app = app
        self.manifest = manifest

        self.window = tk.Toplevel(app.root)
        self.window.title("Review Manifest")
        self.window.geometry("900x640")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            self.window.configure(bg=colors["app_background"])

        self.build_window(warnings)

    def build_window(self, warnings):
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)

        text_box = tk.Text(frame, wrap="word")
        text_box.pack(fill="both", expand=True)

        self.app.style_text_widget(text_box)
        text_box.insert("1.0", self.app.build_review_text(self.manifest, warnings))
        text_box.configure(state="disabled")

        button_frame = ttk.Frame(self.window, padding=10)
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="Confirm Export",
            command=lambda: self.app.export_reviewed_manifest(self.manifest, self.window)
        ).pack(side="right", padx=4)

        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side="right", padx=4)


class VerificationReviewWindow:
    def __init__(self, app, report):
        self.app = app
        self.report = report

        self.window = tk.Toplevel(app.root)
        self.window.title("Review Verification")
        self.window.geometry("950x650")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            self.window.configure(bg=colors["app_background"])

        self.build_window()

    def build_window(self):
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)

        text_box = tk.Text(frame, wrap="word")
        text_box.pack(fill="both", expand=True)

        self.app.style_text_widget(text_box)

        summary = self.report.get("summary", {})
        original = self.report.get("original_manifest", {})
        case_info = original.get("case_info", {})

        lines = []
        lines.append("HASH MANIFEST VERIFICATION REVIEW")
        lines.append("=" * 80)
        lines.append("")
        lines.append("ORIGINAL MANIFEST")
        lines.append("-" * 80)
        lines.append(f"Case Number: {case_info.get('case_number', '')}")
        lines.append(f"Agency Case Number: {case_info.get('agency_case_number', '')}")
        lines.append(f"Source Description: {case_info.get('source_description', '')}")
        lines.append(f"Original Created At: {original.get('created_at', '')}")
        lines.append("")
        lines.append("VERIFICATION SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Results: {summary.get('total_results', 0)}")
        lines.append(f"Matched: {summary.get('matched', 0)}")
        lines.append(f"Hash Mismatch: {summary.get('hash_mismatch', 0)}")
        lines.append(f"Missing From Current Selection: {summary.get('missing_from_current_selection', 0)}")
        lines.append(f"New File Not In Original Manifest: {summary.get('new_file_not_in_original_manifest', 0)}")
        lines.append(f"Errors: {summary.get('errors', 0)}")
        lines.append("")
        lines.append("Click Confirm Export to write the selected verification formats. JSON is always created.")

        text_box.insert("1.0", "\n".join(lines))
        text_box.configure(state="disabled")

        button_frame = ttk.Frame(self.window, padding=10)
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="Confirm Export",
            command=lambda: self.app.export_verification_report(self.report, self.window)
        ).pack(side="right", padx=4)

        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side="right", padx=4)


class CompareWindow:
    def __init__(self, app):
        self.app = app
        self.manifest_a = None
        self.manifest_b = None
        self.manifest_a_path = ""
        self.manifest_b_path = ""

        self.window = tk.Toplevel(app.root)
        self.window.title("Compare Two Manifests")
        self.window.geometry("900x480")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            self.window.configure(bg=colors["app_background"])

        self.build_window()

    def build_window(self):
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Manifest A").grid(row=0, column=0, sticky="w", pady=5)
        self.manifest_a_var = tk.StringVar(value="No Manifest A loaded.")
        ttk.Label(frame, textvariable=self.manifest_a_var, style="Muted.TLabel", wraplength=680).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(frame, text="Load Manifest A", command=self.load_manifest_a).grid(row=0, column=2, padx=4, pady=5)

        ttk.Label(frame, text="Manifest B").grid(row=1, column=0, sticky="w", pady=5)
        self.manifest_b_var = tk.StringVar(value="No Manifest B loaded.")
        ttk.Label(frame, textvariable=self.manifest_b_var, style="Muted.TLabel", wraplength=680).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(frame, text="Load Manifest B", command=self.load_manifest_b).grid(row=1, column=2, padx=4, pady=5)

        ttk.Label(frame, text="Compare Notes").grid(row=2, column=0, sticky="nw", pady=8)

        self.notes_text = tk.Text(frame, height=10, width=70)
        self.notes_text.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=8)
        self.app.style_text_widget(self.notes_text)

        note = (
            "Compare Mode compares two saved manifest JSON files. It does not hash current files. "
            "Use Verification Mode when you want to hash current files and compare them to a prior manifest."
        )
        ttk.Label(frame, text=note, wraplength=820).grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))

        button_frame = ttk.Frame(self.window, padding=10)
        button_frame.pack(fill="x")

        ttk.Button(button_frame, text="Review Compare", command=self.review_compare).pack(side="right", padx=4)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side="right", padx=4)

    def load_manifest_a(self):
        path = filedialog.askopenfilename(
            title="Select Manifest A JSON",
            filetypes=[
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )

        if not path:
            return

        try:
            self.manifest_a = load_compare_manifest_json(path)
            self.manifest_a_path = path
            self.manifest_a_var.set(path)
        except Exception as e:
            messagebox.showerror("Load Manifest A Error", f"Could not load Manifest A.\n\nDetails:\n{e}")

    def load_manifest_b(self):
        path = filedialog.askopenfilename(
            title="Select Manifest B JSON",
            filetypes=[
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )

        if not path:
            return

        try:
            self.manifest_b = load_compare_manifest_json(path)
            self.manifest_b_path = path
            self.manifest_b_var.set(path)
        except Exception as e:
            messagebox.showerror("Load Manifest B Error", f"Could not load Manifest B.\n\nDetails:\n{e}")

    def review_compare(self):
        if not self.manifest_a:
            messagebox.showerror("Missing Manifest A", "Load Manifest A before comparing.")
            return

        if not self.manifest_b:
            messagebox.showerror("Missing Manifest B", "Load Manifest B before comparing.")
            return

        notes = self.notes_text.get("1.0", "end").strip()

        report = build_compare_report(
            manifest_a=self.manifest_a,
            manifest_b=self.manifest_b,
            manifest_a_path=self.manifest_a_path,
            manifest_b_path=self.manifest_b_path,
            technician=self.app.technician_var.get(),
            notes=notes
        )

        CompareReviewWindow(self.app, report)
        self.window.destroy()


class CompareReviewWindow:
    def __init__(self, app, report):
        self.app = app
        self.report = report

        self.window = tk.Toplevel(app.root)
        self.window.title("Review Manifest Compare")
        self.window.geometry("950x650")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            self.window.configure(bg=colors["app_background"])

        self.build_window()

    def build_window(self):
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)

        text_box = tk.Text(frame, wrap="word")
        text_box.pack(fill="both", expand=True)

        self.app.style_text_widget(text_box)

        summary = self.report.get("summary", {})
        manifest_a = self.report.get("manifest_a", {})
        manifest_b = self.report.get("manifest_b", {})
        case_a = manifest_a.get("case_info", {})
        case_b = manifest_b.get("case_info", {})

        lines = []
        lines.append("HASH MANIFEST COMPARE REVIEW")
        lines.append("=" * 80)
        lines.append("")
        lines.append("MANIFEST A")
        lines.append("-" * 80)
        lines.append(f"Case Number: {case_a.get('case_number', '')}")
        lines.append(f"Source Description: {case_a.get('source_description', '')}")
        lines.append(f"Created At: {manifest_a.get('created_at', '')}")
        lines.append("")
        lines.append("MANIFEST B")
        lines.append("-" * 80)
        lines.append(f"Case Number: {case_b.get('case_number', '')}")
        lines.append(f"Source Description: {case_b.get('source_description', '')}")
        lines.append(f"Created At: {manifest_b.get('created_at', '')}")
        lines.append("")
        lines.append("COMPARE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Results: {summary.get('total_results', 0)}")
        lines.append(f"Matched: {summary.get('matched', 0)}")
        lines.append(f"Hash Mismatch: {summary.get('hash_mismatch', 0)}")
        lines.append(f"Only in Manifest A: {summary.get('only_in_manifest_a', 0)}")
        lines.append(f"Only in Manifest B: {summary.get('only_in_manifest_b', 0)}")
        lines.append(f"Errors: {summary.get('errors', 0)}")
        lines.append("")
        lines.append("Click Confirm Export to write the selected compare formats. JSON is always created.")

        text_box.insert("1.0", "\n".join(lines))
        text_box.configure(state="disabled")

        button_frame = ttk.Frame(self.window, padding=10)
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="Confirm Export",
            command=lambda: self.app.export_compare_report(self.report, self.window)
        ).pack(side="right", padx=4)

        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side="right", padx=4)


class AboutWindow:
    def __init__(self, app):
        self.app = app

        self.window = tk.Toplevel(app.root)
        self.window.title(f"About {APP_NAME}")
        self.window.geometry("820x640")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            configure_toplevel(self.window, colors)

        self.build_window()

    def build_window(self):
        frame = ttk.Frame(self.window, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, text=f"{APP_NAME} v{APP_VERSION}", style="Title.TLabel").grid(row=0, column=0, sticky="w")

        about_text = tk.Text(frame, wrap="word", height=24)
        about_text.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        self.app.style_text_widget(about_text)

        content = f"""BYTECASE VERIFY

{APP_SUBTITLE}

Part of the {SUITE_NAME} toolset by {PUBLISHER_NAME}
Product domain: {PRODUCT_DOMAIN}

PURPOSE

ByteCase Verify helps examiners create saved hash manifests, generate reportable integrity documentation, and later rehash files to compare against prior manifests.

The tool supports three core workflows:
- Generate a new hash manifest from selected files or folders
- Verify current files against a prior manifest JSON
- Compare two saved manifest JSON files

PLATFORM IDEOLOGY

ByteCase tools are built around a simple principle:

Bake in best practices, structure, and guidance while preserving enough flexibility for agencies to customize their workflow.

ByteCase Verify is designed for repeatable file integrity documentation. It helps preserve the ability to return to a saved manifest months later, rehash current files, compare results, and generate clear integrity documentation for review or court preparation.

WHAT THIS TOOL DOES NOT DO

ByteCase Verify does not acquire physical drives, image media, control write blockers, parse evidence, determine evidentiary relevance, prove file origin, interpret file contents, identify user activity, or replace examiner review.

Matching hashes support file integrity comparison. They do not explain what a file means, where it came from, who created it, or whether it is relevant to an investigation.

OUTPUT PHILOSOPHY

Default root folder:
{get_default_output_root()}

Typical output structure:
{DEFAULT_ROOT_FOLDER_NAME}/<case_number>/{TOOL_FOLDER_NAME}/

ByteCase Verify separates outputs by workflow:
- manifests/
- verifications/
- comparisons/

ATTRIBUTION

Created by Matt McBride.
Published under the Forensics Byte brand.

Suite: {SUITE_NAME}
Tool: {APP_NAME}
Domain: {PRODUCT_DOMAIN}
"""

        about_text.insert("1.0", content)
        about_text.configure(state="disabled")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, sticky="e")
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side="right")


class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.settings = app.settings.copy()

        self.window = tk.Toplevel(app.root)
        self.window.title("Settings")
        self.window.geometry("760x690")
        self.window.transient(app.root)
        self.window.grab_set()

        self.apply_window_theme()
        self.build_window()
        self.load_values()

    def apply_window_theme(self):
        colors = getattr(self.app, "theme_colors", None)

        if colors:
            self.window.configure(bg=colors["app_background"])

    def build_window(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self.window)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.build_appearance_tab(notebook)
        self.build_department_tab(notebook)
        self.build_output_tab(notebook)
        self.build_branding_tab(notebook)
        self.build_hash_defaults_tab(notebook)
        self.build_report_defaults_tab(notebook)

        button_frame = ttk.Frame(self.window, padding=10)
        button_frame.grid(row=1, column=0, sticky="e")

        ttk.Button(button_frame, text="Save", command=self.save).grid(row=0, column=0, padx=4)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).grid(row=0, column=1, padx=4)

    def build_appearance_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Appearance")
        frame.columnconfigure(1, weight=1)

        self.theme_var = tk.StringVar(value="dark")

        ttk.Label(frame, text="Theme").grid(row=0, column=0, sticky="w", pady=5)

        ttk.Combobox(
            frame,
            textvariable=self.theme_var,
            values=THEME_DISPLAY_NAMES,
            state="readonly"
        ).grid(row=0, column=1, sticky="ew", pady=5)

    def build_department_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Department")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        self.department_name_var = tk.StringVar()
        self.unit_name_var = tk.StringVar()
        self.default_technician_var = tk.StringVar()

        self.add_labeled_entry(frame, "Department / Agency Name", self.department_name_var, 0)
        self.add_labeled_entry(frame, "Unit Name", self.unit_name_var, 1)

        ttk.Label(frame, text="Default Technician").grid(row=2, column=0, sticky="w", pady=5)

        self.default_technician_combo = ttk.Combobox(
            frame,
            textvariable=self.default_technician_var,
            values=[],
            state="normal"
        )
        self.default_technician_combo.grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(frame, text="Technician List").grid(row=3, column=0, sticky="nw", pady=5)

        self.technicians_text = tk.Text(frame, height=12, width=50)
        self.technicians_text.grid(row=3, column=1, sticky="nsew", pady=5)
        self.app.style_text_widget(self.technicians_text)

        ttk.Label(
            frame,
            text="Enter one technician per line. These names appear in the Technician dropdown.",
            wraplength=680
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def build_output_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Output / Storage")
        frame.columnconfigure(1, weight=1)

        self.base_output_dir_var = tk.StringVar()

        ttk.Label(frame, text="ByteCase Output Root").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=self.base_output_dir_var).grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Button(frame, text="Browse", command=self.browse_base_output_dir).grid(row=0, column=2, sticky="e", padx=4)
        ttk.Button(frame, text="Clear", command=lambda: self.base_output_dir_var.set("")).grid(row=0, column=3, sticky="e", padx=4)

        helper_text = (
            "Leave blank to use the default local ByteCase folder:\n"
            f"{get_default_output_root()}\n\n"
            "When a custom root is selected, ByteCase creates case folders directly inside that location:\n"
            f"<custom root>\\<case_number>\\{TOOL_FOLDER_NAME}\\\n\n"
            "ByteCase Verify separates outputs by mode under the verify folder:\n"
            "manifests\\, verifications\\, and comparisons\\"
        )

        ttk.Label(frame, text=helper_text, style="Muted.TLabel", wraplength=680, justify="left").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(14, 0)
        )

    def build_branding_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Report Branding")
        frame.columnconfigure(1, weight=1)

        self.patch_image_path_var = tk.StringVar()

        self.add_labeled_entry(frame, "Patch / Logo Image Path", self.patch_image_path_var, 0)

        ttk.Button(frame, text="Browse", command=self.browse_patch_image).grid(row=0, column=2, sticky="e", padx=4)
        ttk.Button(frame, text="Clear", command=lambda: self.patch_image_path_var.set("")).grid(row=0, column=3, sticky="e", padx=4)

    def build_hash_defaults_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Hash Defaults")

        self.default_md5_var = tk.BooleanVar()
        self.default_sha1_var = tk.BooleanVar()
        self.default_sha256_var = tk.BooleanVar()
        self.default_include_explanation_var = tk.BooleanVar()
        self.default_include_generation_method_var = tk.BooleanVar()

        ttk.Checkbutton(frame, text="MD5 checked by default", variable=self.default_md5_var).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Checkbutton(frame, text="SHA-1 checked by default", variable=self.default_sha1_var).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Checkbutton(frame, text="SHA-256 checked by default", variable=self.default_sha256_var).grid(row=2, column=0, sticky="w", pady=4)

        ttk.Separator(frame).grid(row=3, column=0, sticky="ew", pady=8)

        ttk.Checkbutton(
            frame,
            text="Include hash generation method in TXT report by default",
            variable=self.default_include_generation_method_var
        ).grid(row=4, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            frame,
            text="Include hashing explanation in TXT report by default",
            variable=self.default_include_explanation_var
        ).grid(row=5, column=0, sticky="w", pady=4)

    def build_report_defaults_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Report Defaults")
        frame.columnconfigure(0, weight=1)

        self.default_include_signature_block_var = tk.BooleanVar(value=True)
        self.export_txt_var = tk.BooleanVar(value=True)
        self.export_csv_var = tk.BooleanVar(value=False)
        self.export_docx_var = tk.BooleanVar(value=True)
        self.export_xlsx_var = tk.BooleanVar(value=False)

        ttk.Label(frame, text="Default Export Formats", style="Title.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Checkbutton(
            frame,
            text="TXT report",
            variable=self.export_txt_var
        ).grid(row=1, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            frame,
            text="CSV spreadsheet-friendly export",
            variable=self.export_csv_var
        ).grid(row=2, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            frame,
            text="DOCX report",
            variable=self.export_docx_var
        ).grid(row=3, column=0, sticky="w", pady=4)

        ttk.Checkbutton(
            frame,
            text="XLSX workbook",
            variable=self.export_xlsx_var
        ).grid(row=4, column=0, sticky="w", pady=4)

        ttk.Label(
            frame,
            text=(
                "JSON is always exported because ByteCase Verify uses JSON manifests for later "
                "verification and comparison. Disable optional formats here to keep export folders cleaner."
            ),
            style="Muted.TLabel",
            wraplength=680,
            justify="left"
        ).grid(row=5, column=0, sticky="w", pady=(8, 14))

        ttk.Separator(frame).grid(row=6, column=0, sticky="ew", pady=8)

        ttk.Checkbutton(
            frame,
            text="Include report signature block by default",
            variable=self.default_include_signature_block_var
        ).grid(row=7, column=0, sticky="w", pady=4)

        note = (
            "The signature block is optional per report. When enabled, TXT and DOCX reports "
            "include technician and reviewer signature lines. XLSX records whether the option was enabled."
        )

        ttk.Label(frame, text=note, wraplength=680).grid(row=8, column=0, sticky="w", pady=(12, 0))

    def add_labeled_entry(self, parent, label_text, variable, row):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)

    def load_values(self):
        appearance = self.settings.get("appearance", {})
        output_paths = self.settings.get("output_paths", {})
        report_branding = self.settings.get("report_branding", {})
        hash_defaults = self.settings.get("hash_defaults", {})
        report_defaults = self.settings.get("report_defaults", {})
        technicians = self.settings.get("technicians", [])

        if not isinstance(technicians, list):
            technicians = []

        self.theme_var.set(display_theme_preference(appearance.get("theme", "system")))

        self.department_name_var.set(self.settings.get("department_name", ""))
        self.unit_name_var.set(self.settings.get("unit_name", ""))
        self.default_technician_var.set(self.settings.get("default_technician", ""))

        self.default_technician_combo["values"] = technicians

        self.technicians_text.delete("1.0", "end")
        self.technicians_text.insert("1.0", "\n".join(technicians))

        self.base_output_dir_var.set(output_paths.get("base_output_dir", ""))

        self.patch_image_path_var.set(report_branding.get("patch_image_path", ""))

        self.default_md5_var.set(bool(hash_defaults.get("md5", True)))
        self.default_sha1_var.set(bool(hash_defaults.get("sha1", False)))
        self.default_sha256_var.set(bool(hash_defaults.get("sha256", True)))
        self.default_include_explanation_var.set(bool(hash_defaults.get("include_hashing_explanation", True)))
        self.default_include_generation_method_var.set(bool(hash_defaults.get("include_hash_generation_method", True)))

        self.default_include_signature_block_var.set(
            bool(report_defaults.get("include_signature_block", True))
        )
        self.export_txt_var.set(bool(report_defaults.get("export_txt", True)))
        self.export_csv_var.set(bool(report_defaults.get("export_csv", False)))
        self.export_docx_var.set(bool(report_defaults.get("export_docx", True)))
        self.export_xlsx_var.set(bool(report_defaults.get("export_xlsx", False)))

    def get_technicians_from_text(self):
        raw_text = self.technicians_text.get("1.0", "end").strip()
        technicians = []
        seen = set()

        for line in raw_text.splitlines():
            technician = line.strip()

            if not technician:
                continue

            key = technician.lower()

            if key not in seen:
                technicians.append(technician)
                seen.add(key)

        default_technician = self.default_technician_var.get().strip()

        if default_technician:
            key = default_technician.lower()

            if key not in seen:
                technicians.insert(0, default_technician)

        return technicians

    def browse_base_output_dir(self):
        folder = filedialog.askdirectory(title="Select Base Output Folder")

        if folder:
            self.base_output_dir_var.set(folder)

    def browse_patch_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Patch / Logo Image",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg *.jpeg"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self.patch_image_path_var.set(file_path)

    def save(self):
        technicians = self.get_technicians_from_text()

        self.settings["appearance"] = {
            "theme": theme_preference_from_display(self.theme_var.get())
        }

        self.settings["department_name"] = self.department_name_var.get().strip()
        self.settings["unit_name"] = self.unit_name_var.get().strip()
        self.settings["default_technician"] = self.default_technician_var.get().strip()
        self.settings["technicians"] = technicians

        self.settings["output_paths"] = {
            "base_output_dir": self.base_output_dir_var.get().strip(),
            "use_shared_bytecase_root": True
        }

        self.settings["report_branding"] = {
            "patch_image_path": self.patch_image_path_var.get().strip()
        }

        self.settings["hash_defaults"] = {
            "md5": self.default_md5_var.get(),
            "sha1": self.default_sha1_var.get(),
            "sha256": self.default_sha256_var.get(),
            "include_hashing_explanation": self.default_include_explanation_var.get(),
            "include_hash_generation_method": self.default_include_generation_method_var.get()
        }

        self.settings["report_defaults"] = {
            "include_signature_block": self.default_include_signature_block_var.get(),
            "export_txt": self.export_txt_var.get(),
            "export_csv": self.export_csv_var.get(),
            "export_docx": self.export_docx_var.get(),
            "export_xlsx": self.export_xlsx_var.get(),
            "export_json": True
        }

        save_settings(self.settings)
        self.app.refresh_after_settings_save()
        self.window.destroy()
        messagebox.showinfo("Settings Saved", "Settings saved successfully.")


def main():
    root = tk.Tk()
    HashManifestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()