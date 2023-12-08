import tkinter as tk
from tkinter import ttk
import asyncio
from bleak import BleakScanner, BleakClient
import threading
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class ESP32App:
    def __init__(self, window):
        self.window = window
        self.loop = asyncio.new_event_loop()
        window.title("ESP32 Control Panel")


        # BLE Device Dropdown
        ttk.Label(window, text="Select BLE Device:").grid(column=0, row=0)
        self.ble_device = tk.StringVar()
        self.ble_device_dropdown = ttk.Combobox(window, width=17, textvariable=self.ble_device)
        self.ble_device_dropdown.grid(column=1, row=0)
        self.ble_device_dropdown['values'] = ['Scanning...']


        # Connect Button
        self.connect_button = ttk.Button(window, text="Connect", command=self.async_connect)
        self.connect_button.grid(column=2, row=0)

        # Turn On Appliance Button
        self.open_button = ttk.Button(window, text="Turn On Appliance", command=lambda: self.async_send_command("On"))
        self.open_button.grid(column=0, row=1)

        # Turn Off Appliance Button
        self.close_button = ttk.Button(window, text="Turn Off Appliance", command=lambda: self.async_send_command("Off"))
        self.close_button.grid(column=1, row=1)

        # Status Label
        self.status_label = ttk.Label(window, text="Status: Not Connected")
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
