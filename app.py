import sys
import csv
import numpy as np
import pydicom
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as pdf_canvas
from PIL import Image, ImageTk
import os
from datetime import datetime  # This is the correct import for datetime

class DicomCanvas(FigureCanvasTkAgg):
    def __init__(self, parent):
        self.fig = Figure(figsize=(6, 5), dpi=100, facecolor='#2b2b2b' if ctk.get_appearance_mode() == "Dark" else '#f0f0f0')
        super().__init__(self.fig, master=parent)
        
        self.ax = self.fig.add_subplot(111)
        self.dicom_data = None
        self.start_point = None
        self.end_point = None
        self.temp_line = None
        self.temp_text = None
        self.measurements = []

        # Set dark mode colors if needed
        if ctk.get_appearance_mode() == "Dark":
            self.fig.patch.set_facecolor('#2b2b2b')
            self.ax.set_facecolor('#2b2b2b')
            self.ax.tick_params(colors='white')
            self.ax.xaxis.label.set_color('white')
            self.ax.yaxis.label.set_color('white')
            self.ax.spines['bottom'].set_color('white')
            self.ax.spines['top'].set_color('white') 
            self.ax.spines['right'].set_color('white')
            self.ax.spines['left'].set_color('white')

        self.mpl_connect("button_press_event", self.on_mouse_press)
        self.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.mpl_connect("button_release_event", self.on_mouse_release)
        self.mpl_connect("scroll_event", self.on_scroll)

        self.panning = False
        self.last_event = None
        
        self.fig.tight_layout()
        self.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def load_dicom(self, path):
        self.dicom_data = pydicom.dcmread(path)
        self.ax.clear()
        pixel_array = self.dicom_data.pixel_array

        if hasattr(self.dicom_data, 'RescaleSlope') and hasattr(self.dicom_data, 'RescaleIntercept'):
            pixel_array = pixel_array * self.dicom_data.RescaleSlope + self.dicom_data.RescaleIntercept

        self.ax.imshow(pixel_array, cmap='gray')
        self.ax.set_title("Click and drag to measure", color='white' if ctk.get_appearance_mode() == "Dark" else 'black')
        self.ax.axis("off")
        
        # Update colors for dark mode
        if ctk.get_appearance_mode() == "Dark":
            self.ax.title.set_color('white')
        
        self.draw()

    def on_mouse_press(self, event):
        if event.inaxes != self.ax:
            return
        if event.button == 3:  # Right click
            self.panning = True
            self.last_event = event
            return
        if event.button == 1:  # Left click
            self.start_point = (event.xdata, event.ydata)
            self.temp_line = None
            self.temp_text = None

    def on_mouse_move(self, event):
        if event.inaxes != self.ax:
            return
        if self.panning and self.last_event:
            dx = event.xdata - self.last_event.xdata
            dy = event.ydata - self.last_event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.last_event = event
            self.draw()
            return
        if self.start_point is None:
            return
        self.end_point = (event.xdata, event.ydata)
        if self.temp_line:
            self.temp_line.remove()
        if self.temp_text:
            self.temp_text.remove()

        x0, y0 = self.start_point
        x1, y1 = self.end_point
        length = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        self.temp_line = self.ax.plot([x0, x1], [y0, y1], 'r-', linewidth=2)[0]
        self.temp_text = self.ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"{length:.1f}", 
                                    color='yellow', fontsize=10, bbox=dict(facecolor='black', alpha=0.5))
        self.draw()

    def on_mouse_release(self, event):
        if self.panning:
            self.panning = False
            self.last_event = None
            return
        if event.inaxes != self.ax or self.start_point is None:
            return

        x0, y0 = self.start_point
        x1, y1 = event.xdata, event.ydata
        length = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)

        # Modern dialog with CTk
        dialog = ctk.CTkInputDialog(text="Enter name for this measurement:", title="Name this marking")
        name = dialog.get_input()
        if not name or not name.strip():
            name = f"Measurement {len(self.measurements)+1}"

        self.ax.plot([x0, x1], [y0, y1], 'g-', linewidth=1.5)
        self.ax.plot(x0, y0, 'go', markersize=6)
        self.ax.plot(x1, y1, 'go', markersize=6)
        self.ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"{name}: {length:.1f}", 
                    color='yellow', fontsize=10, bbox=dict(facecolor='black', alpha=0.5))
        self.draw()

        self.measurements.append([name, x0, y0, x1, y1, length])
        self.save_measurements_to_csv()

        self.start_point = None
        self.end_point = None
        self.temp_line = None
        self.temp_text = None

    def on_scroll(self, event):
        base_scale = 1.1
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata
        
        if xdata is not None and ydata is not None:
            new_xlim = [xdata - (xdata - xlim[0]) * scale_factor, xdata + (xlim[1] - xdata) * scale_factor]
            new_ylim = [ydata - (ydata - ylim[0]) * scale_factor, ydata + (ylim[1] - ydata) * scale_factor]
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)
            self.draw()

    def save_measurements_to_csv(self):
        with open("measurements.csv", mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Start X", "Start Y", "End X", "End Y", "Length (px)"])
            writer.writerows(self.measurements)


class DicomViewer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Modern DICOM Viewer")
        self.geometry("1600x900")
        self.minsize(1200, 700)
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create left and right frames with modern styling
        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="nsew")
        
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=0, column=1, padx=(5, 15), pady=15, sticky="nsew")
        self.right_frame.grid_remove()  # Hide initially
        
        # Configure left frame grid
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=1)
        
        # Top control panel with modern buttons
        self.control_panel = ctk.CTkFrame(self.left_frame, height=60, corner_radius=8)
        self.control_panel.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.control_panel.grid_columnconfigure(0, weight=1)
        self.control_panel.grid_columnconfigure(1, weight=1)
        self.control_panel.grid_columnconfigure(2, weight=1)
        
        # Add modern buttons with icons (placeholder - you can add actual icons)
        self.open_button = ctk.CTkButton(
            self.control_panel, 
            text="Open DICOM", 
            command=self.open_dicom_file,
            fg_color="#3a7ebf",
            hover_color="#325882",
            corner_radius=8
        )
        self.open_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        self.export_button = ctk.CTkButton(
            self.control_panel,
            text="Export Measurements",
            command=self.export_measurements,
            fg_color="#2d7d46",
            hover_color="#245c36",
            corner_radius=8
        )
        self.export_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        self.generate_button = ctk.CTkButton(
            self.control_panel,
            text="Generate Report",
            command=self.generate_report,
            fg_color="#7d3e2d",
            hover_color="#5c2e22",
            corner_radius=8
        )
        self.generate_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        
        # Create canvas frame with modern styling
        self.canvas_frame = ctk.CTkFrame(self.left_frame, corner_radius=8)
        self.canvas_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        
        # Create canvas
        self.canvas = DicomCanvas(self.canvas_frame)
        
        # Modern toolbar frame
        self.toolbar_frame = ctk.CTkFrame(self.left_frame, height=40, corner_radius=8)
        self.toolbar_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # Convert toolbar to CTk compatible
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
        self.toolbar.update()
        
        # Status bar with modern look
        self.status_bar = ctk.CTkFrame(self.left_frame, height=30, corner_radius=0)
        self.status_bar.grid(row=3, column=0, padx=0, pady=0, sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar, 
            text="Ready", 
            anchor="w",
            font=("Segoe UI", 10)
        )
        self.status_label.grid(row=0, column=0, padx=15, pady=5, sticky="ew")
        
        # Right frame components (report panel)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=0)
        
        # Report header
        self.report_header = ctk.CTkLabel(
            self.right_frame, 
            text="Measurement Report", 
            font=("Segoe UI", 14, "bold"),
            anchor="w"
        )
        self.report_header.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        
        # Modern textbox with scrollbar
        self.report_text = ctk.CTkTextbox(
            self.right_frame, 
            wrap="word",
            font=("Segoe UI", 12),
            activate_scrollbars=True,
            corner_radius=8
        )
        self.report_text.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")
        self.report_text.insert("1.0", "Measurement report will be generated here...\n\n")
        
        # PDF button with modern style
        self.save_pdf_button = ctk.CTkButton(
            self.right_frame,
            text="Save as PDF",
            command=self.save_report_as_pdf,
            fg_color="#3a7ebf",
            hover_color="#325882",
            corner_radius=8
        )
        self.save_pdf_button.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        
        # Add menu bar (not natively supported in CTk, so we use tkinter)
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        
        # File menu
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Open DICOM", command=self.open_dicom_file)
        file_menu.add_command(label="Export Measurements", command=self.export_measurements)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        
        # View menu
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        view_menu.add_command(label="Toggle Report Panel", command=self.toggle_report_panel)
        view_menu.add_separator()
        view_menu.add_command(label="Light Mode", command=lambda: ctk.set_appearance_mode("Light"))
        view_menu.add_command(label="Dark Mode", command=lambda: ctk.set_appearance_mode("Dark"))
        view_menu.add_command(label="System Mode", command=lambda: ctk.set_appearance_mode("System"))
        self.menu_bar.add_cascade(label="View", menu=view_menu)
        
        # Help menu
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        self.menu_bar.add_cascade(label="Help", menu=help_menu)

    def toggle_report_panel(self):
        if self.right_frame.winfo_ismapped():
            self.right_frame.grid_remove()
        else:
            self.right_frame.grid()

    def open_dicom_file(self):
        file_path = filedialog.askopenfilename(
            title="Open DICOM File",
            filetypes=[("DICOM Files", "*.dcm"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                self.status_label.configure(text=f"Loading: {os.path.basename(file_path)}...")
                self.update()
                self.canvas.load_dicom(file_path)
                self.status_label.configure(text=f"Loaded: {os.path.basename(file_path)}")
            except Exception as e:
                self.status_label.configure(text=f"Error loading file: {str(e)}")

    def export_measurements(self):
        if not hasattr(self.canvas, 'measurements') or not self.canvas.measurements:
            self.status_label.configure(text="No measurements to export")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Save Measurements As"
        )
        if file_path:
            try:
                with open(file_path, mode="w", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(["Name", "Start X", "Start Y", "End X", "End Y", "Length (px)"])
                    writer.writerows(self.canvas.measurements)
                self.status_label.configure(text=f"Measurements saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.status_label.configure(text=f"Export failed: {str(e)}")

    def generate_report(self):
        try:
            if not hasattr(self.canvas, 'measurements') or not self.canvas.measurements:
                self.report_text.delete("1.0", tk.END)
                self.report_text.insert("1.0", "No measurements available. Please make some measurements first.")
                return
                
            with open("measurements.csv", "r") as file:
                reader = csv.DictReader(file)
                lines = ["=== Measurement Report ===\n\n"]
                lines.append(f"Total Measurements: {len(self.canvas.measurements)}\n\n")
                
                for i, row in enumerate(reader, 1):
                    lines.append(f"Measurement #{i}\n")
                    lines.append(f"Name: {row['Name']}\n")
                    lines.append(f"Length: {row['Length (px)']} pixels\n")
                    lines.append(f"Coordinates: ({row['Start X']}, {row['Start Y']}) to ({row['End X']}, {row['End Y']})\n\n")
                
                report_text = "".join(lines)
                
                self.report_text.delete("1.0", tk.END)
                self.report_text.insert("1.0", report_text)
                
                # Save screenshot with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Fixed: using datetime.now()
                screenshot_path = f"screenshot_{timestamp}.png"
                self.canvas.fig.savefig(screenshot_path, dpi=150, bbox_inches='tight', facecolor=self.canvas.fig.get_facecolor())
                
                self.report_text.insert(tk.END, f"\n\nScreenshot saved as: {screenshot_path}")
                self.status_label.configure(text=f"Report generated with {len(self.canvas.measurements)} measurements")
                
        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", f"Failed to generate report:\n{str(e)}")
            self.status_label.configure(text="Report generation failed")

        # Show the report panel
        self.right_frame.grid()

    def save_report_as_pdf(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Fixed: using datetime.now()
            pdf_path = f"report_{timestamp}.pdf"
            
            c = pdf_canvas.Canvas(pdf_path, pagesize=letter)
            text = self.report_text.get("1.0", tk.END)
            
            # Set up PDF styles
            c.setFont("Helvetica", 12)
            c.setFillColorRGB(0, 0, 0)  # Black text
            
            # Write report header
            c.drawString(50, 750, "DICOM Measurement Report")
            c.setFont("Helvetica", 10)
            c.drawString(50, 730, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")  # Fixed
            c.line(50, 725, 550, 725)
            
            # Write report text
            y = 700
            for line in text.split("\n"):
                if line.startswith("===") or line.startswith("Measurement #"):
                    c.setFont("Helvetica-Bold", 10)
                else:
                    c.setFont("Helvetica", 10)
                
                c.drawString(50, y, line)
                y -= 15
                if y < 100:
                    c.showPage()
                    y = 750
                    c.setFont("Helvetica", 10)
            
            # Insert screenshot image if available
            screenshot_files = [f for f in os.listdir() if f.startswith("screenshot_")]
            if screenshot_files:
                latest_screenshot = max(screenshot_files, key=os.path.getctime)
                try:
                    img = Image.open(latest_screenshot)
                    img_width, img_height = img.size
                    aspect = img_height / float(img_width)
                    
                    c.showPage()
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(50, 750, "DICOM Image with Measurements")
                    
                    # Scale image to fit page width with some margins
                    max_width = 500
                    max_height = max_width * aspect
                    if max_height > 600:
                        max_height = 600
                        max_width = max_height / aspect
                    
                    c.drawImage(latest_screenshot, (letter[0]-max_width)/2, 750-max_height-20, 
                               width=max_width, height=max_height, mask='auto')
                except Exception as e:
                    c.drawString(50, 730, f"Could not insert image: {str(e)}")
            
            c.save()
            self.status_label.configure(text=f"Report saved as {pdf_path}")
        except Exception as e:
            self.status_label.configure(text=f"PDF save failed: {str(e)}")

    def show_about(self):
        about_text = """Modern DICOM Viewer
        
Version 1.0
Developed with Python, CustomTkinter, and pydicom
        
Features:
- DICOM image viewing
- Interactive measurements
- Report generation
- PDF export
        
© 2023 Medical Imaging Tools"""
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("About")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        textbox = ctk.CTkTextbox(dialog, wrap="word")
        textbox.pack(fill="both", expand=True, padx=20, pady=20)
        textbox.insert("1.0", about_text)
        textbox.configure(state="disabled")
        
        button = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
        button.pack(pady=(0, 20))


if __name__ == "__main__":
    app = DicomViewer()
    app.mainloop()