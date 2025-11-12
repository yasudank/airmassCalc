import argparse
import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
import tkinter.font as tkFont
import re
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time, TimeDelta
import astropy.units as u
import sys

def parse_ope_file(file_path):
    """
    Parses an .ope file to extract celestial object data.
    """
    objects_data = {}
    pattern = re.compile(r'^(?P<key>\w+)=OBJECT="(?P<object_name>\w+)" RA=(?P<ra>[0-9.+\-]+) DEC=(?P<dec>[0-9.+\-]+) EQUINOX=.*')
    try:
        with open(file_path, 'r') as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    data = match.groupdict()
                    ra_str = data['ra']
                    dec_str = data['dec']
                    ra_formatted = f"{ra_str[0:2]}h{ra_str[2:4]}m{ra_str[4:]}s"
                    dec_sign = dec_str[0]
                    if dec_sign not in ('+', '-'):
                        dec_sign = '+'
                        dec_abs = dec_str
                    else:
                        dec_abs = dec_str[1:]
                    dec_formatted = f"{dec_sign}{dec_abs[0:2]}d{dec_abs[2:4]}m{dec_abs[4:]}s"
                    coord = SkyCoord(ra_formatted, dec_formatted, frame='icrs')
                    objects_data[data['key']] = coord
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        sys.exit(1) # Exit if file not found
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1) # Exit on other errors
    return objects_data

class AirmassCalculatorApp(ThemedTk):
    def __init__(self, objects_data):
        super().__init__(theme="arc")
        self.objects_data = objects_data
        self.title("Airmass Calculator")
        self.geometry("850x650")

        # Set fonts for the theme
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(size=12)
        self.option_add("*Font", default_font)

        style = ttk.Style()
        style.configure('Bold.TLabel', font=(default_font.actual("family"), 14, 'bold'))
        style.configure('Header.TLabel', font=(default_font.actual("family"), 12, 'bold'))

        self.location = EarthLocation(lat=19.825556 * u.deg, lon=-155.476111 * u.deg, height=4139 * u.m)

        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        ttk.Label(list_frame, text="Celestial Objects", style='Bold.TLabel').grid(row=0, column=0, sticky=tk.W)
        
        # Use ttk.Treeview for a more modern list
        self.object_tree = ttk.Treeview(list_frame, columns=('name',), show='headings', height=15)
        self.object_tree.heading('name', text='Object Name')
        self.object_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.rowconfigure(1, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.object_tree.yview)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        self.object_tree.config(yscrollcommand=scrollbar.set)

        details_frame = ttk.Frame(main_frame)
        details_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        main_frame.columnconfigure(1, weight=2)

        ttk.Label(details_frame, text="Observation Details", style='Bold.TLabel').grid(row=0, column=0, columnspan=3, sticky=tk.W)
        
        self.info_labels = {}
        self.setup_details_panel(details_frame)

        for name in sorted(self.objects_data.keys()):
            self.object_tree.insert('', tk.END, values=(name,))
        
        self.object_tree.bind('<<TreeviewSelect>>', self.on_object_select)
        self.update_calculations()

    def setup_details_panel(self, parent_frame):
        # Basic Info
        info_items = ["Object Name", "RA (J2000)", "DEC (J2000)"]
        for i, item in enumerate(info_items):
            ttk.Label(parent_frame, text=f"{item}:").grid(row=i+1, column=0, sticky=tk.W, pady=2)
            self.info_labels[item] = ttk.Label(parent_frame, text="-", anchor="w", width=40)
            self.info_labels[item].grid(row=i+1, column=1, columnspan=2, sticky=tk.W, pady=2)

        # Separator
        ttk.Separator(parent_frame, orient='horizontal').grid(row=len(info_items)+1, column=0, columnspan=3, sticky='ew', pady=10)

        # Time Offset Input
        offset_frame = ttk.Frame(parent_frame)
        offset_frame.grid(row=len(info_items)+2, column=0, columnspan=3, sticky='ew')
        ttk.Label(offset_frame, text="Time Offset (min):").grid(row=0, column=0, sticky=tk.W)
        self.offset_var = tk.StringVar(value="20")
        ttk.Entry(offset_frame, textvariable=self.offset_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

        # Headers for Current and Future
        ttk.Label(parent_frame, text="Current", style='Header.TLabel').grid(row=len(info_items)+3, column=1, sticky=tk.W, pady=5)
        ttk.Label(parent_frame, text="Future", style='Header.TLabel').grid(row=len(info_items)+3, column=2, sticky=tk.W, pady=5)

        # Calculation rows
        calc_items = ["Time (UTC)", "Altitude", "Azimuth", "Airmass"]
        for i, item in enumerate(calc_items):
            row = len(info_items) + 4 + i
            ttk.Label(parent_frame, text=f"{item}:").grid(row=row, column=0, sticky=tk.W, pady=2)
            # Current
            self.info_labels[f"{item}_current"] = ttk.Label(parent_frame, text="-", anchor="w", width=20)
            self.info_labels[f"{item}_current"].grid(row=row, column=1, sticky=tk.W, pady=2)
            # Future
            self.info_labels[f"{item}_future"] = ttk.Label(parent_frame, text="-", anchor="w", width=20)
            self.info_labels[f"{item}_future"].grid(row=row, column=2, sticky=tk.W, pady=2)

    def on_object_select(self, event=None):
        selection = self.object_tree.selection()
        if not selection: return
        self.selected_object_name = self.object_tree.item(selection[0])['values'][0]
        self.update_display()

    def update_calculations(self):
        self.current_time = Time.now()
        self.update_display()
        self.after(1000, self.update_calculations)

    def update_display(self):
        self.info_labels["Time (UTC)_current"].config(text=f"{self.current_time.utc.iso.split('.')[0]}")

        if not hasattr(self, 'selected_object_name'): return

        coord = self.objects_data[self.selected_object_name]
        self.info_labels["Object Name"].config(text=self.selected_object_name)
        self.info_labels["RA (J2000)"].config(text=coord.ra.to_string(unit=u.hour, sep='hms', precision=2))
        self.info_labels["DEC (J2000)"].config(text=coord.dec.to_string(unit=u.deg, sep='dms', precision=2))

        # Current calculations
        altaz_frame = AltAz(obstime=self.current_time, location=self.location)
        object_altaz = coord.transform_to(altaz_frame)
        self.info_labels["Altitude_current"].config(text=f"{object_altaz.alt.deg:.4f}°")
        self.info_labels["Azimuth_current"].config(text=f"{object_altaz.az.deg:.4f}°")
        self.info_labels["Airmass_current"].config(text=f"{object_altaz.secz:.4f}" if object_altaz.alt.deg > 0 else "Below Horizon")

        # Future calculations
        try:
            offset_minutes = float(self.offset_var.get())
            time_delta = TimeDelta(offset_minutes * 60, format='sec')
            future_time = self.current_time + time_delta
            
            future_altaz_frame = AltAz(obstime=future_time, location=self.location)
            future_object_altaz = coord.transform_to(future_altaz_frame)

            self.info_labels["Time (UTC)_future"].config(text=f"{future_time.utc.iso.split('.')[0]}")
            self.info_labels["Altitude_future"].config(text=f"{future_object_altaz.alt.deg:.4f}°")
            self.info_labels["Azimuth_future"].config(text=f"{future_object_altaz.az.deg:.4f}°")
            self.info_labels["Airmass_future"].config(text=f"{future_object_altaz.secz:.4f}" if future_object_altaz.alt.deg > 0 else "Below Horizon")
        except (ValueError, TypeError):
            for item in ["Time (UTC)", "Altitude", "Azimuth", "Airmass"]:
                self.info_labels[f"{item}_future"].config(text="Invalid Offset")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Airmass Calculator GUI")
    parser.add_argument('--ope', type=str, help='Path to the .ope file containing celestial object data')
    args = parser.parse_args()
    
    ope_file = args.ope if args.ope else '2025-11-12.ope'
    celestial_objects = parse_ope_file(ope_file)
    
    if not celestial_objects:
        print("Could not start GUI: No celestial objects were parsed.")
    else:
        app = AirmassCalculatorApp(celestial_objects)
        app.mainloop()