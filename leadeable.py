import requests
import gspread
import time
from datetime import datetime
import customtkinter as ctk
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from PIL import Image, ImageTk
from google.oauth2.credentials import Credentials
import logging

# Configure logging for tracking errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google API settings (statically defined)
GOOGLE_CLIENT_ID = "YOUR GOOGLE CLIENT ID"
GOOGLE_CLIENT_SECRET = "YOUR CLIENT SECRET"
GOOGLE_REDIRECT_URI = "http://localhost:8000/callback"

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if "/callback" in self.path:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Authentication successful! Close this window.")
            
            if "code" in params:
                server = self.server
                server.context["google_code"] = params["code"][0]
        else:
            self.send_error(404)

class SyncConfig:
    def __init__(self, name, fb_access_token, ad_account_id, form_id, sheet_id, frequency_minutes, google_token):
        self.name = name
        self.fb_access_token = fb_access_token
        self.ad_account_id = ad_account_id
        self.form_id = form_id
        self.sheet_id = sheet_id
        self.frequency_minutes = frequency_minutes
        self.google_token = google_token
        self.running = False
        self.thread = None

class LeadableApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Leadable")
        self.root.geometry("900x700")  # Wider window
        self.root.configure(bg="#FFFFFF")  # Completely white background
        ctk.set_appearance_mode("light")  # Light mode
        self.google_token = None
        self.sheets = []
        self.syncs = []

        # Load icon (only as window icon, removed from the interface)
        icon_pil = Image.open("leadable_icon.png").convert("RGBA")  # Ensure it's in RGBA mode
        self.icon_photo = ImageTk.PhotoImage(icon_pil.resize((32, 32), Image.Resampling.LANCZOS))  # Tkinter PhotoImage
        self.root.iconphoto(True, self.icon_photo)  # Set window icon

        # Fixed frequency options
        self.frequency_options = {
            "5 minutes": 5,
            "10 minutes": 10,
            "30 minutes": 30,
            "1 hour": 60,
            "2 hours": 120,
            "6 hours": 360,
            "12 hours": 720,
            "1 day": 1440
        }

        # Main frame (left content and right list)
        self.main_container = ctk.CTkFrame(root, fg_color="#FFFFFF", corner_radius=0, border_width=0, bg_color="#FFFFFF")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Left content (new synchronizations)
        self.main_frame = ctk.CTkFrame(self.main_container, fg_color="#FFFFFF", corner_radius=0, border_width=0, bg_color="#FFFFFF", width=560)
        self.main_frame.pack(side="left", fill="both", expand=False, padx=0, pady=0)

        # Top frame (new synchronization) - modern, minimalistic style
        self.frame = ctk.CTkFrame(self.main_frame, fg_color="#FFFFFF", corner_radius=12, border_width=0, bg_color="#FFFFFF")
        self.frame.pack(pady=0, padx=0, fill="both", expand=True)

        # Facebook Access Token
        self.fb_token_label = ctk.CTkLabel(self.frame, text="Facebook Access Token", text_color="#333333", font=("Inter", 12))
        self.fb_token_label.grid(row=0, column=0, padx=20, pady=16, sticky="w")
        self.fb_token_entry = ctk.CTkEntry(self.frame, width=300, fg_color="#F8F9FA", text_color="#333333", border_color="#B0B0B0", corner_radius=8, font=("Inter", 12))
        self.fb_token_entry.grid(row=0, column=1, padx=20, pady=16)

        # Ad Account ID
        self.ad_account_label = ctk.CTkLabel(self.frame, text="Ad Account ID", text_color="#333333", font=("Inter", 12))
        self.ad_account_label.grid(row=1, column=0, padx=20, pady=16, sticky="w")
        self.ad_account_entry = ctk.CTkEntry(self.frame, width=300, fg_color="#F8F9FA", text_color="#333333", border_color="#B0B0B0", corner_radius=8, font=("Inter", 12))
        self.ad_account_entry.grid(row=1, column=1, padx=20, pady=16)

        # Form ID
        self.form_label = ctk.CTkLabel(self.frame, text="Form ID", text_color="#333333", font=("Inter", 12))
        self.form_label.grid(row=2, column=0, padx=20, pady=16, sticky="w")
        self.form_entry = ctk.CTkEntry(self.frame, width=300, fg_color="#F8F9FA", text_color="#333333", border_color="#B0B0B0", corner_radius=8, font=("Inter", 12))
        self.form_entry.grid(row=2, column=1, padx=20, pady=16)

        # Google Login
        self.google_label = ctk.CTkLabel(self.frame, text="Google", text_color="#333333", font=("Inter", 12))
        self.google_label.grid(row=3, column=0, padx=20, pady=16, sticky="w")
        self.google_login_button = ctk.CTkButton(self.frame, text="Sign In", command=self.google_login, fg_color="#0013FF", hover_color="#0033FF", corner_radius=8, text_color="#FFFFFF", font=("Inter", 12), height=32, width=120)
        self.google_login_button.grid(row=3, column=1, padx=20, pady=16)

        self.sheet_label = ctk.CTkLabel(self.frame, text="Select Sheet", text_color="#333333", font=("Inter", 12))
        self.sheet_label.grid(row=4, column=0, padx=20, pady=16, sticky="w")
        self.sheet_dropdown = ctk.CTkComboBox(self.frame, values=[""], state="disabled", width=300, fg_color="#FFFFFF", text_color="#333333", dropdown_fg_color="#FFFFFF", dropdown_text_color="#333333", border_color="#B0B0B0", button_color="#0013FF", button_hover_color="#0033FF", font=("Inter", 12), corner_radius=8)
        self.sheet_dropdown.grid(row=4, column=1, padx=20, pady=16)

        # Frequency
        self.freq_label = ctk.CTkLabel(self.frame, text="Frequency", text_color="#333333", font=("Inter", 12))
        self.freq_label.grid(row=5, column=0, padx=20, pady=16, sticky="w")
        self.frequency_dropdown = ctk.CTkComboBox(self.frame, values=list(self.frequency_options.keys()), width=300, fg_color="#FFFFFF", text_color="#333333", dropdown_fg_color="#FFFFFF", dropdown_text_color="#333333", border_color="#B0B0B0", button_color="#0013FF", button_hover_color="#0033FF", font=("Inter", 12), corner_radius=8)
        self.frequency_dropdown.grid(row=5, column=1, padx=20, pady=16)
        self.frequency_dropdown.set("1 hour")

        # Synchronization Name
        self.name_label = ctk.CTkLabel(self.frame, text="Synchronization Name", text_color="#333333", font=("Inter", 12))
        self.name_label.grid(row=6, column=0, padx=20, pady=16, sticky="w")
        self.name_entry = ctk.CTkEntry(self.frame, width=300, fg_color="#FFFFFF", text_color="#333333", border_color="#B0B0B0", placeholder_text="e.g. Campaign1", placeholder_text_color="#666666", font=("Inter", 12), corner_radius=8)
        self.name_entry.grid(row=6, column=1, padx=20, pady=16)

        # Create button - modern, minimalistic
        self.create_button = ctk.CTkButton(self.frame, text="Create", command=self.create_sync, fg_color="#0013FF", hover_color="#0033FF", corner_radius=8, text_color="#FFFFFF", font=("Inter", 14, "bold"), height=40, width=120)
        self.create_button.grid(row=7, column=1, padx=20, pady=20, sticky="e")

        # Synchronizations list - modern, minimalistic style, on the right, with scrollbar
        self.list_frame = ctk.CTkFrame(self.main_container, fg_color="#FFFFFF", corner_radius=12, border_width=0, bg_color="#FFFFFF", width=300)
        self.list_frame.pack(side="right", fill="both", expand=False, padx=0, pady=0)

        self.list_label = ctk.CTkLabel(self.list_frame, text="Synchronizations", font=("Inter", 18, "bold"), text_color="#0013FF")
        self.list_label.pack(pady=20)

        # Scrollable frame for synchronizations
        self.sync_canvas = ctk.CTkCanvas(self.list_frame, bg="#FFFFFF", highlightthickness=0)
        self.sync_canvas.pack(side="left", fill="both", expand=True)

        self.sync_scrollbar = ctk.CTkScrollbar(self.list_frame, orientation="vertical", command=self.sync_canvas.yview)
        self.sync_scrollbar.pack(side="right", fill="y")

        self.sync_frame = ctk.CTkFrame(self.sync_canvas, fg_color="#FFFFFF", corner_radius=0, border_width=0)
        self.sync_canvas.create_window((0, 0), window=self.sync_frame, anchor="nw")

        self.sync_frame.bind("<Configure>", lambda e: self.sync_canvas.configure(scrollregion=self.sync_canvas.bbox("all")))
        self.sync_canvas.configure(yscrollcommand=self.sync_scrollbar.set)

        self.sync_list = []  # List of synchronization widgets

        # Status
        self.status_label = ctk.CTkLabel(root, text="Status: Stopped", text_color="#666666", font=("Inter", 12))
        self.status_label.pack(pady=20)

    def google_login(self):
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&scope=https://www.googleapis.com/auth/spreadsheets+https://www.googleapis.com/auth/drive.readonly&response_type=code&access_type=offline"
        webbrowser.open(auth_url)
        
        server = HTTPServer(("localhost", 8000), OAuthHandler)
        server.context = {"google": True}
        server.handle_request()
        
        if "google_code" in server.context:
            code = server.context["google_code"]
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "code": code,
                "grant_type": "authorization_code"
            }
            response = requests.post(token_url, data=data).json()
            self.google_token = response.get("access_token")
            if self.google_token:
                self.google_login_button.configure(text="OK", state="disabled")
                self.load_google_sheets()
            else:
                logger.error(f"Token retrieval error: {response.get('error', 'Unknown error')}")

    def load_google_sheets(self):
        try:
            url = "https://www.googleapis.com/drive/v3/files?q=mimeType='application/vnd.google-apps.spreadsheet' AND trashed=false"
            headers = {"Authorization": f"Bearer {self.google_token}"}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                self.sheets = [{"id": file["id"], "name": file["name"]} for file in files if "name" in file]
                self.sheet_dropdown.configure(values=[sheet["name"] for sheet in self.sheets], state="readonly")
                if self.sheets:
                    self.sheet_dropdown.set(self.sheets[0]["name"])
                else:
                    self.sheet_dropdown.configure(values=["No available sheets"], state="disabled")
                    logger.warning("No available Google Sheets found.")
            else:
                logger.error(f"API error when listing Sheets: {response.status_code} - {response.text}")
                self.sheet_dropdown.configure(values=["Error occurred"], state="disabled")
        except Exception as e:
            logger.error(f"Error loading Sheets: {str(e)}")
            self.sheet_dropdown.configure(values=["Error occurred"], state="disabled")

    def create_sync(self):
        try:
            name = self.name_entry.get() or f"Sync_{len(self.syncs) + 1}"
            fb_access_token = self.fb_token_entry.get()
            ad_account_id = self.ad_account_entry.get()
            form_id = self.form_entry.get()
            frequency_text = self.frequency_dropdown.get()
            frequency_minutes = self.frequency_options[frequency_text]

            if not fb_access_token or not ad_account_id or not form_id:
                raise ValueError("Fill in all Facebook fields!")
            if not self.google_token:
                raise ValueError("Sign in to Google first!")
            
            selected_sheet = next((s for s in self.sheets if s["name"] == self.sheet_dropdown.get()), None)
            if not selected_sheet:
                raise ValueError("Select a sheet!")

            sync = SyncConfig(name, fb_access_token, ad_account_id, form_id, selected_sheet["id"], frequency_minutes, self.google_token)
            self.syncs.append(sync)
            self.update_sync_list()
            self.start_sync(sync)
        except ValueError as e:
            ctk.CTkMessageBox(master=self.root, title="Error", message=str(e), icon="warning")

    def update_sync_list(self):
        # Clear previous widgets
        for widget in self.sync_list:
            widget.destroy()
        self.sync_list.clear()

        # Add new synchronizations with icons and animations
        for i, sync in enumerate(self.syncs):
            frame = ctk.CTkFrame(self.sync_frame, fg_color="#FFFFFF", corner_radius=0, border_width=0)
            frame.pack(fill="x", pady=8)

            # Synchronization name and details
            label = ctk.CTkLabel(frame, text=f"{i+1}. {sync.name} - {sync.frequency_minutes} min", text_color="#333333", font=("Inter", 12))
            label.pack(side="left", padx=20, pady=10)

            # Function buttons (Unicode icons)
            buttons_frame = ctk.CTkFrame(frame, fg_color="#FFFFFF", corner_radius=0, border_width=0)
            buttons_frame.pack(side="right")

            # Timing edit (⏱️ icon, with animation)
            edit_button = ctk.CTkButton(buttons_frame, text="⏱️", command=lambda s=sync: self.edit_timing(s), fg_color="#0013FF", hover_color="#0033FF", corner_radius=6, text_color="#FFFFFF", font=("Inter", 16, "bold"), height=32, width=32)
            edit_button.pack(side="left", padx=5)
            edit_button.bind("<Enter>", lambda e, b=edit_button: b.configure(fg_color="#0033FF"))  # Hover animation
            edit_button.bind("<Leave>", lambda e, b=edit_button: b.configure(fg_color="#0013FF"))

            # Start/Stop (with animation)
            if sync.running:
                stop_button = ctk.CTkButton(buttons_frame, text="⏹️", command=lambda s=sync: self.stop_sync(s), fg_color="#FF4D4F", hover_color="#FF3335", corner_radius=6, text_color="#FFFFFF", font=("Inter", 16, "bold"), height=32, width=32)
                stop_button.pack(side="left", padx=5)
                stop_button.bind("<Enter>", lambda e, b=stop_button: b.configure(fg_color="#FF3335"))  # Hover animation
                stop_button.bind("<Leave>", lambda e, b=stop_button: b.configure(fg_color="#FF4D4F"))
            else:
                start_button = ctk.CTkButton(buttons_frame, text="▶️", command=lambda s=sync: self.start_sync(s), fg_color="#0013FF", hover_color="#0033FF", corner_radius=6, text_color="#FFFFFF", font=("Inter", 16, "bold"), height=32, width=32)
                start_button.pack(side="left", padx=5)
                start_button.bind("<Enter>", lambda e, b=start_button: b.configure(fg_color="#0033FF"))  # Hover animation
                start_button.bind("<Leave>", lambda e, b=start_button: b.configure(fg_color="#0013FF"))

            # Delete (🗑️ icon, with animation)
            delete_button = ctk.CTkButton(buttons_frame, text="🗑️", command=lambda s=sync: self.delete_sync(s, None), fg_color="#FF4D4F", hover_color="#FF3335", corner_radius=6, text_color="#FFFFFF", font=("Inter", 16, "bold"), height=32, width=32)
            delete_button.pack(side="left", padx=5)
            delete_button.bind("<Enter>", lambda e, b=delete_button: b.configure(fg_color="#FF3335"))  # Hover animation
            delete_button.bind("<Leave>", lambda e, b=delete_button: b.configure(fg_color="#FF4D4F"))

            # Separator line
            separator = ctk.CTkFrame(self.sync_frame, fg_color="#E0E0E0", height=1)
            separator.pack(fill="x", pady=8)

            self.sync_list.append(frame)

    def edit_timing(self, sync):
        """Edit timing in a separate window"""
        timing_window = ctk.CTkToplevel(self.root)
        timing_window.title(f"{sync.name} Timing Edit")
        timing_window.geometry("300x200")
        timing_window.configure(bg="#FFFFFF")

        ctk.CTkLabel(timing_window, text="New Frequency", text_color="#333333", font=("Inter", 14)).pack(pady=15)
        freq_dropdown = ctk.CTkComboBox(timing_window, values=list(self.frequency_options.keys()), width=250, fg_color="#FFFFFF", text_color="#333333", dropdown_fg_color="#FFFFFF", dropdown_text_color="#333333", border_color="#B0B0B0", button_color="#0013FF", button_hover_color="#0033FF", font=("Inter", 12), corner_radius=8)
        freq_dropdown.pack(pady=10)
        current_freq = next(k for k, v in self.frequency_options.items() if v == sync.frequency_minutes)
        freq_dropdown.set(current_freq)

        def save_timing():
            sync.frequency_minutes = self.frequency_options[freq_dropdown.get()]
            self.update_sync_list()
            timing_window.destroy()

        ctk.CTkButton(timing_window, text="Save", command=save_timing, fg_color="#0013FF", hover_color="#0033FF", corner_radius=8, text_color="#FFFFFF", font=("Inter", 14, "bold"), height=40).pack(pady=20)

    def start_sync(self, sync):
        if not sync.running:
            sync.running = True
            sync.thread = threading.Thread(target=self.sync_loop, args=(sync,), daemon=True)
            sync.thread.start()
            self.update_sync_list()

    def stop_sync(self, sync):
        if sync.running:
            sync.running = False
            if sync.thread:
                sync.thread.join(timeout=1)
            self.update_sync_list()

    def delete_sync(self, sync, window):
        if sync in self.syncs:
            self.stop_sync(sync)
            self.syncs.remove(sync)
            self.update_sync_list()
            if window:
                window.destroy()

    def setup_google_sheets(self, sync):
        creds = Credentials(token=sync.google_token)
        client = gspread.authorize(creds)
        return client.open_by_key(sync.sheet_id).sheet1

    def get_facebook_leads(self, sync):
        url = f"https://graph.facebook.com/v20.0/{sync.form_id}/leads"
        params = {"access_token": sync.fb_access_token, "fields": "created_time,field_data"}
        response = requests.get(url, params=params).json()
        
        if "data" not in response:
            self.update_status(f"Error with Facebook API: {response.get('error', 'Unknown error')}")
            return []
        return response["data"]

    def process_lead_data(self, leads):
        processed_leads = []
        for lead in leads:
            lead_dict = {"date": lead["created_time"], "name": "", "email": "", "other_fields": []}
            for field in lead["field_data"]:
                if field["name"] == "full_name":
                    lead_dict["name"] = field["values"][0]
                elif field["name"] == "email":
                    lead_dict["email"] = field["values"][0]
                else:
                    lead_dict["other_fields"].append(f"{field['name']}: {field['values'][0]}")
            processed_leads.append(lead_dict)
        return processed_leads

    def update_google_sheets(self, sheet, leads):
        headers = ["Date", "Name", "Email", "Other Fields"]
        if not sheet.row_values(1):
            sheet.append_row(headers)
        
        existing_dates = sheet.col_values(1)[1:]
        for lead in leads:
            if lead["date"] not in existing_dates:
                row = [lead["date"], lead["name"], lead["email"], "; ".join(lead["other_fields"])]
                sheet.append_row(row)
                self.update_status(f"New lead: {lead['name']}")

    def sync_loop(self, sync):
        try:
            sheet = self.setup_google_sheets(sync)
            while sync.running:
                try:
                    self.update_status(f"Checking ({sync.name}): {datetime.now().strftime('%H:%M:%S')}")
                    leads = self.get_facebook_leads(sync)
                    processed_leads = self.process_lead_data(leads)
                    self.update_google_sheets(sheet, processed_leads)
                    self.update_status(f"Waiting ({sync.name})...")
                    time.sleep(sync.frequency_minutes * 60)
                except Exception as e:
                    self.update_status(f"Error ({sync.name}): {str(e)}")
                    time.sleep(300)
        except Exception as e:
            self.update_status(f"Google Sheets error ({sync.name}): {str(e)}")
            self.stop_sync(sync)

    def update_status(self, message):
        self.status_label.configure(text=message)

if __name__ == "__main__":
    root = ctk.CTk()
    app = LeadableApp(root)
    root.mainloop()
