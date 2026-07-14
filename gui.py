import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hash_core import (
    build_manifest,
    collect_files,
    get_total_size_bytes,
    hash_files,
    save_manifest_outputs
)
from settings_service import (
    APP_NAME,
    APP_VERSION,
    ensure_directories,
    load_or_create_settings,
    save_settings
)
from validators import (
    format_bytes,
    summarize_hash_results,
    validate_hash_request,
    validate_manifest_for_export
)


class HashManifestApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1200x760")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.settings = load_or_create_settings()

        self.selected_files = []
        self.selected_folders = []
        self.hash_results = []
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
        theme = self.settings.get("appearance", {}).get("theme", "dark")

        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        if theme == "light":
            colors = {
                "bg": "#f5f5f5",
                "text": "#111111",
                "muted": "#444444",
                "accent": "#b8860b",
                "button": "#e6e6e6",
                "button_text": "#111111",
                "field": "#ffffff",
                "field_text": "#111111",
                "tree_bg": "#ffffff",
                "tree_text": "#111111",
                "heading_bg": "#e8e8e8",
                "border": "#c0c0c0"
            }
        else:
            colors = {
                "bg": "#111111",
                "text": "#f2f2f2",
                "muted": "#c0c0c0",
                "accent": "#d4af37",
                "button": "#2a2a2a",
                "button_text": "#f2f2f2",
                "field": "#202020",
                "field_text": "#f2f2f2",
                "tree_bg": "#161616",
                "tree_text": "#f2f2f2",
                "heading_bg": "#2a2a2a",
                "border": "#3a3a3a"
            }

        self.theme_colors = colors
        self.root.configure(bg=colors["bg"])

        style.configure(
            ".",
            background=colors["bg"],
            foreground=colors["text"],
            fieldbackground=colors["field"],
            font=("Segoe UI", 10)
        )

        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["text"])
        style.configure("Title.TLabel", background=colors["bg"], foreground=colors["accent"], font=("Segoe UI", 16, "bold"))
        style.configure("Muted.TLabel", background=colors["bg"], foreground=colors["muted"])

        style.configure(
            "TLabelframe",
            background=colors["bg"],
            foreground=colors["accent"],
            bordercolor=colors["border"]
        )

        style.configure(
            "TLabelframe.Label",
            background=colors["bg"],
            foreground=colors["accent"],
            font=("Segoe UI", 10, "bold")
        )

        style.configure(
            "TButton",
            background=colors["button"],
            foreground=colors["button_text"],
            padding=6,
            borderwidth=1
        )

        style.map(
            "TButton",
            background=[
                ("active", colors["accent"]),
                ("pressed", colors["accent"]),
                ("disabled", colors["button"])
            ],
            foreground=[
                ("active", "#111111"),
                ("pressed", "#111111"),
                ("disabled", colors["muted"])
            ]
        )

        style.configure("TCheckbutton", background=colors["bg"], foreground=colors["text"])
        style.map("TCheckbutton", background=[("active", colors["bg"])], foreground=[("active", colors["accent"])])

        style.configure(
            "TEntry",
            fieldbackground=colors["field"],
            foreground=colors["field_text"],
            insertcolor=colors["accent"]
        )

        style.configure(
            "TCombobox",
            fieldbackground=colors["field"],
            background=colors["button"],
            foreground=colors["field_text"],
            arrowcolor=colors["accent"]
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["field"])],
            foreground=[("readonly", colors["field_text"])],
            background=[("readonly", colors["button"])]
        )

        style.configure("TNotebook", background=colors["bg"], borderwidth=0)

        style.configure(
            "TNotebook.Tab",
            background=colors["button"],
            foreground=colors["text"],
            padding=(10, 5)
        )

        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["accent"])],
            foreground=[("selected", "#111111")]
        )

        style.configure(
            "Treeview",
            background=colors["tree_bg"],
            fieldbackground=colors["tree_bg"],
            foreground=colors["tree_text"],
            rowheight=24
        )

        style.configure(
            "Treeview.Heading",
            background=colors["heading_bg"],
            foreground=colors["accent"],
            font=("Segoe UI", 10, "bold")
        )

        style.map(
            "Treeview",
            background=[("selected", colors["accent"])],
            foreground=[("selected", "#111111")]
        )

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=colors["field"],
            background=colors["accent"],
            bordercolor=colors["field"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"]
        )

        style.configure("TSeparator", background=colors["border"])

    def style_text_widget(self, widget):
        colors = getattr(self, "theme_colors", None)

        if not colors:
            return

        widget.configure(
            background=colors["field"],
            foreground=colors["field_text"],
            insertbackground=colors["accent"],
            selectbackground=colors["accent"],
            selectforeground="#111111",
            relief="solid",
            borderwidth=1
        )

    def build_gui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            top_frame,
            text=f"{APP_NAME} v{APP_VERSION}",
            style="Title.TLabel"
        )
        title_label.grid(row=0, column=0, sticky="w")

        button_frame = ttk.Frame(top_frame)
        button_frame.grid(row=0, column=1, sticky="e")

        ttk.Button(button_frame, text="Settings", command=self.open_settings_window).grid(row=0, column=0, padx=4)
        ttk.Button(button_frame, text="Open Output Folder", command=self.open_output_folder).grid(row=0, column=1, padx=4)

        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        upper_frame = ttk.Frame(main_pane)
        lower_frame = ttk.Frame(main_pane)

        main_pane.add(upper_frame, weight=1)
        main_pane.add(lower_frame, weight=3)

        self.build_input_section(upper_frame)
        self.build_results_section(lower_frame)

    def build_input_section(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        case_frame = ttk.LabelFrame(parent, text="Manifest Information", padding=10)
        case_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        case_frame.columnconfigure(1, weight=1)

        self.case_number_var = tk.StringVar()
        self.agency_case_number_var = tk.StringVar()
        self.technician_var = tk.StringVar()
        self.source_description_var = tk.StringVar()

        self.add_labeled_entry(case_frame, "Case Number", self.case_number_var, 0)
        self.add_labeled_entry(case_frame, "Agency Case Number", self.agency_case_number_var, 1)
        self.add_labeled_entry(case_frame, "Technician", self.technician_var, 2)
        self.add_labeled_entry(case_frame, "Source Description", self.source_description_var, 3)

        notes_label = ttk.Label(case_frame, text="Manifest Notes")
        notes_label.grid(row=4, column=0, sticky="nw", pady=4)

        self.notes_text = tk.Text(case_frame, height=4, width=50)
        self.notes_text.grid(row=4, column=1, sticky="ew", pady=4)
        self.style_text_widget(self.notes_text)

        options_frame = ttk.LabelFrame(parent, text="Hash Options", padding=10)
        options_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        options_frame.columnconfigure(0, weight=1)

        self.md5_var = tk.BooleanVar(value=True)
        self.sha1_var = tk.BooleanVar(value=False)
        self.sha256_var = tk.BooleanVar(value=True)
        self.recursive_var = tk.BooleanVar(value=True)
        self.include_explanation_var = tk.BooleanVar(value=True)
        self.include_generation_method_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="MD5", variable=self.md5_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="SHA-1", variable=self.sha1_var).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="SHA-256", variable=self.sha256_var).grid(row=2, column=0, sticky="w")

        ttk.Separator(options_frame).grid(row=3, column=0, sticky="ew", pady=8)

        ttk.Checkbutton(options_frame, text="Include folders recursively", variable=self.recursive_var).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="Include hash generation method in TXT report", variable=self.include_generation_method_var).grid(row=5, column=0, sticky="w")
        ttk.Checkbutton(options_frame, text="Include hashing explanation in TXT report", variable=self.include_explanation_var).grid(row=6, column=0, sticky="w")

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

        ttk.Button(action_frame, text="Clear Manifest", command=self.clear_manifest).grid(row=0, column=2, padx=4)

        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            style="Horizontal.TProgressbar"
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")

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

        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=16)

        self.results_tree.heading("file_name", text="File Name")
        self.results_tree.heading("size", text="Size")
        self.results_tree.heading("status", text="Status")
        self.results_tree.heading("md5", text="MD5")
        self.results_tree.heading("sha1", text="SHA-1")
        self.results_tree.heading("sha256", text="SHA-256")
        self.results_tree.heading("path", text="Path")

        self.results_tree.column("file_name", width=180, anchor="w")
        self.results_tree.column("size", width=90, anchor="w")
        self.results_tree.column("status", width=90, anchor="w")
        self.results_tree.column("md5", width=220, anchor="w")
        self.results_tree.column("sha1", width=220, anchor="w")
        self.results_tree.column("sha256", width=320, anchor="w")
        self.results_tree.column("path", width=420, anchor="w")

        y_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        x_scroll = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results_tree.xview)

        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def add_labeled_entry(self, parent, label_text, variable, row):
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0, sticky="w", pady=4)

        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)

    def load_defaults_from_settings(self):
        self.technician_var.set(self.settings.get("default_technician", ""))

        hash_defaults = self.settings.get("hash_defaults", {})
        self.md5_var.set(bool(hash_defaults.get("md5", True)))
        self.sha1_var.set(bool(hash_defaults.get("sha1", False)))
        self.sha256_var.set(bool(hash_defaults.get("sha256", True)))
        self.include_explanation_var.set(bool(hash_defaults.get("include_hashing_explanation", True)))
        self.include_generation_method_var.set(bool(hash_defaults.get("include_hash_generation_method", True)))

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
            window.configure(bg=colors["bg"])

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
        file_count = len(self.selected_files)
        folder_count = len(self.selected_folders)

        self.selection_summary_var.set(f"Selected files: {file_count} | Selected folders: {folder_count}")

    def start_hashing(self):
        if self.hashing_active:
            return

        algorithms = self.get_selected_algorithms()

        errors, warnings = validate_hash_request(
            self.selected_files,
            self.selected_folders,
            algorithms
        )

        if errors:
            messagebox.showerror(
                "Hashing Validation Error",
                "Fix the following before hashing:\n\n" + "\n".join(errors)
            )
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

        self.status_var.set(f"Hashing 0 of {len(files)} files...")
        self.current_file_var.set("Preparing...")

        worker = threading.Thread(
            target=self.hashing_worker,
            args=(files, algorithms),
            daemon=True
        )
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
                    current_index = payload.get("current_index", 0)
                    total_files = payload.get("total_files", 0)
                    current_file = payload.get("current_file", "")

                    self.status_var.set(f"Hashing file {current_index} of {total_files}")
                    self.current_file_var.set(f"Current file: {current_file}")

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

                    messagebox.showinfo("Hashing Complete", "Hash manifest results are ready to review.")

                elif message_type == "error":
                    self.hashing_active = False
                    self.hash_button.config(state="normal")
                    self.review_button.config(state="disabled")
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
            source_description=self.source_description_var.get(),
            recursive=self.recursive_var.get(),
            algorithms=self.get_selected_algorithms(),
            include_hashing_explanation=self.include_explanation_var.get(),
            include_hash_generation_method=self.include_generation_method_var.get(),
            notes=notes,
            files=self.hash_results
        )

    def build_review_text(self, manifest, warnings):
        case_info = manifest.get("case_info", {})
        hash_settings = manifest.get("hash_settings", {})
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
        lines.append(f"Technician: {case_info.get('technician', '')}")
        lines.append(f"Source Description: {case_info.get('source_description', '')}")
        lines.append("")

        lines.append("SELECTED INPUT SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Selected Files: {len(self.selected_files)}")
        lines.append(f"Selected Folders: {len(self.selected_folders)}")
        lines.append(f"Recursive Folder Selection: {'Yes' if hash_settings.get('recursive') else 'No'}")
        lines.append(f"Total Files Found: {summary['total_files']}")
        lines.append("")

        lines.append("HASH SETTINGS")
        lines.append("-" * 80)
        algorithms = hash_settings.get("algorithms", [])
        lines.append(f"Algorithms: {', '.join(algorithms) if algorithms else 'None'}")
        lines.append(f"Include Hash Generation Method: {'Yes' if hash_settings.get('include_hash_generation_method') else 'No'}")
        lines.append(f"Include Hashing Explanation: {'Yes' if hash_settings.get('include_hashing_explanation') else 'No'}")
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
        lines.append("Click Confirm Export to write TXT, CSV, DOCX, and JSON outputs.")

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
            messagebox.showerror(
                "Manifest Validation Error",
                "Fix the following before export:\n\n" + "\n".join(errors)
            )
            return

        ReviewWindow(self, manifest, warnings)

    def export_reviewed_manifest(self, manifest, review_window):
        try:
            txt_path, csv_path, docx_path, json_path = save_manifest_outputs(manifest, self.settings)

            review_window.destroy()

            self.status_var.set("Manifest exported successfully.")

            messagebox.showinfo(
                "Manifest Exported",
                "Hash manifest exported successfully.\n\n"
                f"TXT:\n{txt_path}\n\n"
                f"CSV:\n{csv_path}\n\n"
                f"DOCX:\n{docx_path}\n\n"
                f"JSON:\n{json_path}"
            )

        except PermissionError as e:
            messagebox.showerror(
                "Export Error",
                "The manifest could not be exported because a file may be open or locked.\n\n"
                f"Details:\n{e}"
            )

        except OSError as e:
            messagebox.showerror(
                "Export Error",
                f"The manifest could not be exported.\n\nDetails:\n{e}"
            )

        except Exception as e:
            messagebox.showerror(
                "Export Error",
                f"The manifest could not be exported.\n\nDetails:\n{e}"
            )

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
        self.technician_var.set(self.settings.get("default_technician", ""))
        self.source_description_var.set("")
        self.notes_text.delete("1.0", "end")

        self.progress_var.set(0)
        self.status_var.set("Ready.")
        self.current_file_var.set("")
        self.review_button.config(state="disabled")

        self.clear_results_table()
        self.update_selection_summary()

    def open_output_folder(self):
        paths = ensure_directories(self.settings)
        output_dir = paths["reports_dir"]

        try:
            os.startfile(output_dir)
        except OSError as e:
            messagebox.showerror("Open Output Folder Error", str(e))

    def open_settings_window(self):
        SettingsWindow(self)

    def refresh_after_settings_save(self):
        self.settings = load_or_create_settings()
        self.apply_theme()
        self.load_defaults_from_settings()

        if hasattr(self, "notes_text"):
            self.style_text_widget(self.notes_text)


class ReviewWindow:
    def __init__(self, app, manifest, warnings):
        self.app = app
        self.manifest = manifest

        self.window = tk.Toplevel(app.root)
        self.window.title("Review Manifest")
        self.window.geometry("850x600")
        self.window.transient(app.root)
        self.window.grab_set()

        colors = getattr(app, "theme_colors", {})
        if colors:
            self.window.configure(bg=colors["bg"])

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

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.window.destroy
        ).pack(side="right", padx=4)


class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.settings = app.settings.copy()

        self.window = tk.Toplevel(app.root)
        self.window.title("Settings")
        self.window.geometry("740x590")
        self.window.transient(app.root)
        self.window.grab_set()

        self.apply_window_theme()
        self.build_window()
        self.load_values()

    def apply_window_theme(self):
        colors = getattr(self.app, "theme_colors", None)

        if colors:
            self.window.configure(bg=colors["bg"])

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

        theme_combo = ttk.Combobox(
            frame,
            textvariable=self.theme_var,
            values=["dark", "light"],
            state="readonly"
        )
        theme_combo.grid(row=0, column=1, sticky="ew", pady=5)

        note = (
            "Dark mode uses the ForensicsByte black and gold color scheme.\n"
            "Light mode is provided for readability, printing environments, and user preference."
        )

        ttk.Label(frame, text=note, wraplength=660).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(12, 0)
        )

    def build_department_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Department")
        frame.columnconfigure(1, weight=1)

        self.department_name_var = tk.StringVar()
        self.unit_name_var = tk.StringVar()
        self.default_technician_var = tk.StringVar()

        self.add_labeled_entry(frame, "Department / Agency Name", self.department_name_var, 0)
        self.add_labeled_entry(frame, "Unit Name", self.unit_name_var, 1)
        self.add_labeled_entry(frame, "Default Technician", self.default_technician_var, 2)

    def build_output_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Output / Storage")
        frame.columnconfigure(1, weight=1)

        self.base_output_dir_var = tk.StringVar()
        self.reports_folder_name_var = tk.StringVar()
        self.saved_manifests_folder_name_var = tk.StringVar()

        self.add_labeled_entry(frame, "Base Output Folder", self.base_output_dir_var, 0)

        ttk.Button(frame, text="Browse", command=self.browse_base_output_dir).grid(row=0, column=2, sticky="e", padx=4)
        ttk.Button(frame, text="Clear", command=lambda: self.base_output_dir_var.set("")).grid(row=0, column=3, sticky="e", padx=4)

        self.add_labeled_entry(frame, "Reports Folder Name", self.reports_folder_name_var, 1)
        self.add_labeled_entry(frame, "Saved Manifests Folder Name", self.saved_manifests_folder_name_var, 2)

    def build_branding_tab(self, notebook):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text="Report Branding")
        frame.columnconfigure(1, weight=1)

        self.patch_image_path_var = tk.StringVar()

        self.add_labeled_entry(frame, "Patch / Logo Image Path", self.patch_image_path_var, 0)

        ttk.Button(frame, text="Browse", command=self.browse_patch_image).grid(row=0, column=2, sticky="e", padx=4)
        ttk.Button(frame, text="Clear", command=lambda: self.patch_image_path_var.set("")).grid(row=0, column=3, sticky="e", padx=4)

        note = (
            "Recommended format: PNG\n"
            "Supported formats: PNG, JPG, JPEG\n\n"
            "The image path is stored for future report generation support."
        )

        ttk.Label(frame, text=note, wraplength=660).grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(12, 0)
        )

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

        note = (
            "Recommended default: MD5 and SHA-256 enabled, SHA-1 disabled.\n\n"
            "SHA-1 is included as an option for compatibility with older workflows, "
            "but it is disabled by default.\n\n"
            "Hash Generation Method explains what mechanism created the hashes. "
            "Hashing Explanation explains what hash values are."
        )

        ttk.Label(frame, text=note, wraplength=660).grid(row=6, column=0, sticky="w", pady=(12, 0))

    def add_labeled_entry(self, parent, label_text, variable, row):
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0, sticky="w", pady=5)

        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=5)

    def load_values(self):
        appearance = self.settings.get("appearance", {})
        output_paths = self.settings.get("output_paths", {})
        report_branding = self.settings.get("report_branding", {})
        hash_defaults = self.settings.get("hash_defaults", {})

        self.theme_var.set(appearance.get("theme", "dark"))

        self.department_name_var.set(self.settings.get("department_name", ""))
        self.unit_name_var.set(self.settings.get("unit_name", ""))
        self.default_technician_var.set(self.settings.get("default_technician", ""))

        self.base_output_dir_var.set(output_paths.get("base_output_dir", ""))
        self.reports_folder_name_var.set(output_paths.get("reports_folder_name", "output"))
        self.saved_manifests_folder_name_var.set(output_paths.get("saved_manifests_folder_name", "saved_manifests"))

        self.patch_image_path_var.set(report_branding.get("patch_image_path", ""))

        self.default_md5_var.set(bool(hash_defaults.get("md5", True)))
        self.default_sha1_var.set(bool(hash_defaults.get("sha1", False)))
        self.default_sha256_var.set(bool(hash_defaults.get("sha256", True)))
        self.default_include_explanation_var.set(bool(hash_defaults.get("include_hashing_explanation", True)))
        self.default_include_generation_method_var.set(bool(hash_defaults.get("include_hash_generation_method", True)))

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
        self.settings["appearance"] = {
            "theme": self.theme_var.get()
        }

        self.settings["department_name"] = self.department_name_var.get().strip()
        self.settings["unit_name"] = self.unit_name_var.get().strip()
        self.settings["default_technician"] = self.default_technician_var.get().strip()

        self.settings["output_paths"] = {
            "base_output_dir": self.base_output_dir_var.get().strip(),
            "reports_folder_name": self.reports_folder_name_var.get().strip() or "output",
            "saved_manifests_folder_name": self.saved_manifests_folder_name_var.get().strip() or "saved_manifests"
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