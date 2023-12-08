import tkinter as tk
from tkinter import ttk
import asyncio
from bleak import BleakScanner, BleakClient
import threading
from tkinter import messagebox



import random
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import datetime
import pytz 


class ESP32App:
    def __init__(self, window):
        self.window = window
        self.loop = asyncio.new_event_loop()
        window.title("ESP32 Control Panel")
        window.configure(background='#f7f9f7')  # Set the background color

        style = ttk.Style()
        style.configure('TButton', font=('Times New Roman', 14), background='#f7f9f7')  # Button style with new background color
        style.configure('TLabel', font=('Times New Roman', 14), background='#f7f9f7')  # Label style with new background color

        self.appliance_on = False  # Flag to track appliance state
        self.alert_shown = False  # Flag to track if alert has been shown
        # Schedule regular plot updates
        self.schedule_gui_update(self.update_power_consumption_plot)

        # Initialize the start time for measurements
        self.start_time = datetime.datetime.now(pytz.timezone('America/Chicago')).strftime('%I:%M %p')

        self.total_energy_label = ttk.Label(window, text="Total Energy: 0 Wh\nSince: " + self.start_time, background='#f7f9f7')
        self.total_energy_label.grid(column=2, row=5, columnspan=4)

        # Energy limit input box
        self.energy_limit_var = tk.DoubleVar()
        self.energy_limit_entry = ttk.Entry(window, textvariable=self.energy_limit_var, font=('Times New Roman', 14))
        self.energy_limit_entry.grid(column=1, row=4)

        # Set limit button
        self.set_limit_button = ttk.Button(window, text="Set Limit", command=self.set_energy_limit)
        self.set_limit_button.grid(column=2, row=4)

        ble_frame = ttk.Frame(window, padding="6 6 12 12")
        ble_frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        ble_frame.columnconfigure(0, weight=1)
        ble_frame.rowconfigure(0, weight=1)

        plot_frame = ttk.Frame(window, padding="3 3 6 6")
        plot_frame.grid(column=0, row=1, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        scheduler_frame = ttk.Frame(window, padding="3 3 6 6")
        scheduler_frame.grid(column=3, row=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        scheduler_frame.columnconfigure(0, weight=0)
        scheduler_frame.rowconfigure(0, weight=0)

        # Initialize BLE controls in BLE Frame
        self.init_ble_controls(ble_frame)
    
        # Power Consumption Plot
        self.setup_power_consumption_plot(plot_frame)

        # Energy Consumption Plot
        self.setup_energy_consumption_plot(plot_frame)

        # Scheduler
        self.setup_scheduler(scheduler_frame)

    def init_ble_controls(self, frame):
        # BLE Device Dropdown
        ttk.Label(frame, text="Select BLE Device:", background='#f7f9f7').grid(column=0, row=0)
        self.ble_device = tk.StringVar()
        self.ble_device_dropdown = ttk.Combobox(frame, width=20, textvariable=self.ble_device)
        self.ble_device_dropdown.grid(column=1, row=0)
        self.ble_device_dropdown['values'] = ['Scanning...']

        # Connect Button
        self.connect_button = ttk.Button(frame, text="Connect", style='TButton', command=self.async_connect)
        self.connect_button.grid(column=2, row=0)

        # Turn On Appliance Button
        self.open_button = ttk.Button(frame, text="Turn On Appliance", command=lambda: self.async_send_command("On"))
        self.open_button.grid(column=0, row=1)

        # Turn Off Appliance Button
        self.close_button = ttk.Button(frame, text="Turn Off Appliance", command=lambda: self.async_send_command("Off"))
        self.close_button.grid(column=1, row=1)

        # Status Label
        self.status_label = ttk.Label(frame, text="Status: Not Connected")
        self.status_label.grid(column=0, row=2, columnspan=3)

        # BLE variables
        self.devices = []
        self.client = None

        # Start the asyncio event loop in a new thread
        self.thread = threading.Thread(target=self.start_asyncio_loop, args=(self.loop,))
        self.thread.start()

        # Scan for devices (this will now schedule the scan in the asyncio loop)
        self.schedule_asyncio_task(self.scan_for_ble_devices())


    def start_asyncio_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def schedule_asyncio_task(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def scan_for_ble_devices(self):
        self.devices = await BleakScanner.discover()
        device_names = [device.name for device in self.devices if device.name is not None]
        print("Discovered devices:", device_names)  # Debugging line
        self.schedule_gui_update(lambda: self.ble_device_dropdown.config(values=device_names))


    def schedule_gui_update(self, func):
        self.window.after(0, func)

    async def connect(self):
        selected_device_name = self.ble_device.get()
        device = next((d for d in self.devices if d.name == selected_device_name), None)

        if device:
            self.client = BleakClient(device)
            try:
                await self.client.connect()
                self.schedule_gui_update(lambda: self.status_label.config(text="Status: Connected to " + selected_device_name))
            except Exception as e:
                error_message = str(e)
                self.schedule_gui_update(lambda: self.update_status_with_error(error_message))
        else:
            self.schedule_gui_update(lambda: self.status_label.config(text="Status: Device not found"))

    def update_status_with_error(self, error_message):
        self.status_label.config(text=f"Status: Error - {error_message}")

    async def reconnect(self):
        if self.client:
            try:
                await self.client.connect()
                self.schedule_gui_update(lambda: self.status_label.config(text="Status: Reconnected"))
            except Exception as e:
                self.schedule_gui_update(lambda: self.status_label.config(text="Status: Reconnect failed"))

    async def send_command(self, command):
        characteristic_uuid = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
        if self.client and self.client.is_connected:
            try:
                # Attempt to send the command with a timeout of 5 seconds
                await asyncio.wait_for(
                    self.client.write_gatt_char(characteristic_uuid, bytes(command, 'utf-8')),
                    timeout=2.0
                )
                print("Command sent to ESP32")
                print(command)
                if command == "On":
                    self.appliance_on = True
                elif command == "Off":
                    self.appliance_on = False

                # Wait for the response from the ESP32 with a timeout of 5 seconds
                response = await asyncio.wait_for(
                    self.client.read_gatt_char(characteristic_uuid),
                    timeout=5.0
                )
                response = response.decode("utf-8")  # Decode the response
                print(f"ESP32 Response: {response}")
                self.schedule_gui_update(lambda: self.status_label.config(text=f"ESP32 Response: {response}"))
            except asyncio.TimeoutError:
                self.schedule_gui_update(lambda: self.status_label.config(text=f"Could not send command '{command}', please try again"))
                print(f"Timeout while sending command '{command}' to ESP32")
            except Exception as e:
                self.schedule_gui_update(lambda: self.status_label.config(text=f"Status: Error - {e}"))
                print(f"Error while sending command '{command}': {e}")
        else:
            self.schedule_gui_update(lambda: self.status_label.config(text="Status: Not Connected - Attempting reconnect"))
            print("Attempting to reconnect...")
            await self.reconnect()


    def async_connect(self):
        self.schedule_asyncio_task(self.connect())

    def async_send_command(self, command):
        self.schedule_asyncio_task(self.send_command(command))


    def setup_power_consumption_plot(self, frame):
        self.power_consumption_figure = Figure(figsize=(3, 2), dpi=100)  
        # self.power_consumption_figure.subplots_adjust(bottom=0.25)
        self.power_consumption_plot = self.power_consumption_figure.add_subplot(111)
        self.power_consumption_plot.set_title("Power Consumption")
        self.power_consumption_plot.set_xlabel("Time (s)")
        self.power_consumption_plot.set_ylabel("Power (Watts)")

        # Set the y-axis limit to 0-100W
        self.power_consumption_plot.set_ylim(0, 100)

        self.canvas = FigureCanvasTkAgg(self.power_consumption_figure, frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(column=0, row=0, sticky="nsew")  # Place in first row of plot frame

        self.power_data = {'time': [], 'power': []}

    def setup_energy_consumption_plot(self, frame):
        self.energy_consumption_figure = Figure(figsize=(3, 2), dpi=100)  # Smaller size
        self.energy_consumption_figure.subplots_adjust(bottom=0.25)
        self.energy_consumption_plot = self.energy_consumption_figure.add_subplot(111)
        self.energy_consumption_plot.set_title("Energy Consumption")
        self.energy_consumption_plot.set_xlabel("Time (s)")
        self.energy_consumption_plot.set_ylabel("Energy (Wh)") 

        self.energy_canvas = FigureCanvasTkAgg(self.energy_consumption_figure, frame)
        self.energy_canvas_widget = self.energy_canvas.get_tk_widget()
        self.energy_canvas_widget.grid(column=0, row=1, sticky="nsew")  # Place in second row of plot frame


        self.energy_data = {'time': [], 'energy': []}
        self.total_energy = 0.0  # Initialize total energy consumed


    def update_power_consumption_plot(self):
        print("self.appliance_on:", self.appliance_on)
        # if not self.appliance_on:
        #     self.window.after(1000, self.update_power_consumption_plot)
        #     return
        x = 20  # Power in Watts
        # Simulate power consumption data
        self.power_data['time'].append(len(self.power_data['time']))
        self.power_data['power'].append(x + random.uniform(-2.5, 2.5))  # Simulating 60W with randomness

        # Update the plot
        self.power_consumption_plot.clear()
        self.power_consumption_plot.plot(self.power_data['time'], self.power_data['power'])
        self.power_consumption_plot.set_ylim(0, x+20)  # Set y-axis to range from 0 to 100 Watts
        self.power_consumption_plot.set_title("Power Consumption")
        self.power_consumption_plot.set_xlabel("Time (s)")
        self.power_consumption_plot.set_ylabel("Power (Watts)")
        self.canvas.draw()

        # Update Energy Consumption Plot
        power_w = self.power_data['power'][-1]  # Power in Watts
        self.total_energy += power_w * (1 / 3600)  # Increment energy in Wh
        self.energy_data['time'].append(self.power_data['time'][-1])
        self.energy_data['energy'].append(self.total_energy)

        self.energy_consumption_plot.clear()
        self.energy_consumption_plot.plot(self.energy_data['time'], self.energy_data['energy'])
        self.energy_consumption_plot.set_ylim(0, 5)
        self.energy_consumption_plot.set_title("Energy Consumption")
        self.energy_consumption_plot.set_xlabel("Time (s)")
        self.energy_consumption_plot.set_ylabel("Energy (kWh)")
        if hasattr(self, 'energy_limit'):
            self.energy_consumption_plot.axhline(y=self.energy_limit, color='r', linestyle='--')
        if hasattr(self, 'energy_limit') and self.total_energy > self.energy_limit and not self.alert_shown:
            self.show_alert()
            self.alert_shown = True
        self.energy_canvas.draw()

        # Update Total Energy Label
        current_time = datetime.datetime.now(pytz.timezone('America/Chicago')).strftime('%I:%M %p')
        self.total_energy_label.config(text=f"Total Energy: {self.total_energy:.2f} Wh\nSince: {self.start_time} (CST)")


        # Schedule next update
        self.window.after(1000, self.update_power_consumption_plot)

    def set_energy_limit(self):
        self.energy_limit = self.energy_limit_var.get()
        print(f"Energy limit set to: {self.energy_limit} Wh")  # Debugging line

    def show_alert(self):
        tk.messagebox.showwarning("Alert", "Energy Consumption limit passed!")


    def setup_scheduler(self, frame):
        ttk.Label(frame, text="Scheduler", background='#f7f9f7').grid(column=0, row=0, columnspan=2)
        
        ttk.Label(frame, text="Start Time", background='#f7f9f7').grid(column=1, row=1)
        ttk.Label(frame, text="End Time", background='#f7f9f7').grid(column=2, row=1)

        self.schedules = {}
        self.schedule_labels = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            ttk.Label(frame, text=day, background='#f7f9f7').grid(column=0, row=i+2)



            # Start time scale
            start_var = tk.DoubleVar()
            start_scale = tk.Scale(frame, from_=0, to=24, orient='horizontal', variable=start_var, showvalue=False)
            start_scale.grid(column=1, row=i+2)
            
            # End time scale
            end_var = tk.DoubleVar()
            end_scale = tk.Scale(frame, from_=0, to=24, orient='horizontal', variable=end_var, showvalue=False)
            end_scale.grid(column=2, row=i+2)

            self.schedules[day] = (start_var, end_var)

            start_time_label = ttk.Label(frame, text=self.hour_to_time(start_var.get()), background='#f7f9f7')
            start_time_label.grid(column=3, row=i+2)
            end_time_label = ttk.Label(frame, text=self.hour_to_time(end_var.get()), background='#f7f9f7')
            end_time_label.grid(column=4, row=i+2)

            # Bind scale movements to update the time labels
            start_scale.bind("<Motion>", lambda event, s=start_scale, l=start_time_label: 
                             l.config(text=self.hour_to_time(int(s.get()))))
            end_scale.bind("<Motion>", lambda event, s=end_scale, l=end_time_label: 
                           l.config(text=self.hour_to_time(int(s.get()))))

            self.schedules[day] = (start_var, end_var)
            self.schedule_labels[day] = (start_time_label, end_time_label)

        #save button
        self.save_button = ttk.Button(frame, text="Save Schedule", command=self.save_schedule)
        self.save_button.grid(column=0, row=9, columnspan=3)

        self.save_status_label = ttk.Label(frame, text="", background='#f7f9f7')
        self.save_status_label.grid(column=0, row=10)

    def hour_to_time(self, hour):
        """Converts an hour value to a time string."""
        if hour == 24 or hour == 0:
            return "12AM"
        elif hour == 12:
            return "12PM"
        elif hour < 12:
            return f"{hour}AM"
        else:
            return f"{hour-12}PM"

    def save_schedule(self):
        # Implement logic to save the schedule here
        # For now, just display a success message
        self.save_status_label.config(text="Successfully Saved", foreground='green')


def main():
    root = tk.Tk()
    app = ESP32App(root)

    def on_closing():
        app.loop.call_soon_threadsafe(app.loop.stop)  # Stop the asyncio loop
        app.thread.join()  # Wait for the thread to finish
        root.destroy()  # Destroy the window

    root.protocol("WM_DELETE_WINDOW", on_closing)  # Bind the close event
    root.mainloop()

if __name__ == "__main__":
    main()
