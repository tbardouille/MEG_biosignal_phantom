---
meta:
    author: Tim Bardouille
    topic: MEG Dry Phantom
---


# MEG Biosignal Phantom v3 Build Guide

This guide documents the assembly and initial bench testing of the MEG Biosignal Phantom v3 in the Dalhousie Biosignal Laboratory. The build uses an Arduino Uno R3 and three Donders current-driver shields, each containing an eight-channel DAC7578 module. The assembled system provides up to 24 driver channels; the number of connected phantom sources depends on the head and cable configuration.

The Phantom assembly has three main components. 
#### 1. Building the Driver using custom PCBs to generate sinusoidal current matching the characteristics of brain signals.
#### 2. Getting the Phantom frame using a 3-D printer and getting custom PCBs that are designed to work with the frame. 
#### 3. Connection station that connects the driver to the phantom using non-magnetic insulated copper wire. 

# 1. Building the Driver
## 1. Design files and materials

The phantom frame and current-dipole PCBs can be build and ordered using the links below.
Phantom Frame: https://github.com/tbardouille/MEG_biosignal_phantom/tree/main/Contributors/DalBiosignalLab/3dmodels


Current dipole PCBs and HPI: https://github.com/tbardouille/MEG_biosignal_phantom/tree/main/Contributors/Karolinska

<img width="296" height="510" alt="Screenshot 2026-09-29 at 1 12 35 PM" src="https://github.com/user-attachments/assets/2870f3c3-57f5-4823-8ed7-2152dd06af30" />

Use the [Donders contribution directory](https://github.com/tbardouille/MEG_biosignal_phantom/tree/main/Contributors/Donders) for the current-driver design and parts information. Record the exact design revision or Git commit used for each build.

| Item | Quantity for this build | Notes |
| --- | --- | --- |
| Arduino Uno R3 | 1 | Controller used in the build notes |
| Donders Arduino current-driver PCB v1.1 | 3 | Confirm the revision printed on each PCB |
| Adafruit DAC7578 eight-channel breakout | 3 | One module per shield |
| Shield components and stacking headers | As specified by the v1.1 design | Follow the design-specific parts list and schematic |
| Phantom frame and current-dipole PCBs | As specified by the head design | Already assembled at the start of this work |
| Connecting cable and phantom-side connections | As required | Exact connector types and pinout: **to confirm** |
| USB cable and computer | 1 each | For firmware upload and serial output |
| Soldering equipment and inspection tools | As required | Include a multimeter for continuity checks |
| Oscilloscope and suitable test load | As required | For checking output waveforms and current |

Do not substitute the component list from the previous relay-based phantom driver. This build uses DAC7578 shields.
<img width="914" height="514" alt="assembled-shields" src="https://github.com/user-attachments/assets/e58be182-5a72-474a-aeb9-49e6dfb0983a" />

Once you get all the components of the driver, perform a dry fit and make sure that everything is assembled similar to the shield above, However please follow the next steps before soldering.  
## 3. Configure the DAC addresses before mounting the modules

Each shield shares the Arduino's I²C bus. Each DAC7578 must have a different address so the firmware can address the shields independently.

The AD0 solder jumper is on the underside of the Adafruit DAC7578 breakout. Configure it **before** soldering the module onto the driver PCB, while the underside remains accessible.

| AD0 configuration | I²C address |
| --- | --- |
| Leave all three jumper pads unbridged | `0x4C` |
| Bridge the centre pad to the GND pad | `0x48` |
| Bridge the centre pad to the VCC pad | `0x4A` |

The [Adafruit address-jumper instructions](https://learn.adafruit.com/adafruit-dac7578-8-x-channel-12-bit-i2c-dac?view=all#i2c-address-jumper-3193263) describe centre-to-left as GND and centre-to-right as VCC. Use the orientation shown in that guide; left and right change when the board is rotated.

1. Allocate one of the three addresses to each shield.
2. Label each shield with a physical board identifier and its address.
3. Make the required solder bridge on each module. Do not bridge the centre pad to both outer pads.
4. Inspect the jumper for unintended bridges.

**Lesson from this build:** 
#### 1.The first two shields initially used the same default address. The firmware reported them as one device, and the outputs showed the same current and frequency response. The address jumper was difficult to access after assembly, requiring rework. Configure unique addresses first to avoid this problem.
#### 2. Keep the resistor pins after soldering long enough for an alligator clip (for setting the resistors).

## 4. Assemble the current-driver shields

1. Lay out the components for one shield and check them against the v1.1 parts list.
2. Identify component positions and orientations from the schematic and PCB markings. Confirm resistor values against the design; they are not specified in the rough notes.
3. Configure and label the DAC address as described above.
4. Fit the headers, connectors, and circuit components according to the v1.1 assembly design. Check header alignment before completing all solder joints.
5. Install the DAC7578 module in the correct orientation.
6. Inspect all joints for bridges, poor wetting, and loose connections.
7. With power disconnected, check for unintended shorts between supply and ground. Check the output connections against the schematic.
8. Repeat for the remaining shields.

Soldering guidance for the original lab build was provided by Jon, the engineering expert consulted during assembly. Seek experienced help if the board layout or module orientation is unclear.

## 5. Install the Arduino firmware

Use the [uno_dac7578 firmware directory](https://github.com/robertoostenveld/arduino/tree/main/uno_dac7578) for the Uno-based system. The developer correspondence in the notes states that this firmware supports Uno or Leonardo boards and automatically detects one, two, or three shields.

The `rp2040_dac7578` sketch belongs to the earlier RP2040-based controller and was not the firmware selected for this build.

1. Obtain the complete `uno_dac7578` sketch folder, including its accompanying source and header files.
2. Open `uno_dac7578.ino` in the Arduino IDE.
3. Install the dependencies required by the selected firmware revision. The build notes identify **Ticker** and the **DAC7578 library** as compilation dependencies. The notes link Ticker to [sstaub/Ticker](https://github.com/sstaub/Ticker). Confirm the exact DAC7578 library from the firmware includes or documentation before installing it; an unrelated library with a similar name may expose a different API.
4. Select **Arduino Uno** and the connected serial port.
5. Compile the sketch and resolve any missing-library errors.
6. Upload the firmware to the Arduino.
7. Open the Serial Monitor using the baud rate defined in the sketch.
8. Record the firmware commit, IDE version, library versions, and serial startup output.


## 6. Test the shields individually and as a stack

The following sequence is a recommended verification procedure. The source notes show bench testing, but do not record a complete test dataset or acceptance tolerances.

1. Disconnect power before fitting or removing a shield.
2. Connect one shield and check that the firmware detects its expected address. If necessary, use an I²C scanner to verify the address, then restore the driver firmware.
3. Use a suitable test load and command an output using the selected firmware's documented controls.
4. Check the waveform with an oscilloscope and record the output channel, commanded settings, load, and measured response.
5. Repeat for each shield separately.
6. Disconnect power and assemble the stack, checking that the headers are aligned and fully seated.
7. Power the stack and confirm that all three distinct addresses are detected.
8. Activate one addressed output at a time to confirm that commands reach the intended shield and channel. Record whether other outputs behave as expected.

Where current is inferred from a voltage measurement across a known resistor, use `I = V / R`. Record whether the reported voltage and current are peak, peak-to-peak, or RMS values. Do not infer phantom current solely from the commanded DAC value.

<img width="725" height="408" alt="bench-test" src="https://github.com/user-attachments/assets/c6062028-b803-4c38-88c8-e3cc3c7f2dcc" />

*Bench testing shown in the build notes. This image documents the setup; it does not establish calibrated amplitude or frequency accuracy.*

<img width="661" height="1175" alt="three-shield-stack" src="https://github.com/user-attachments/assets/ba41f36a-e894-4845-969e-73a3c63d47be" />

*The build entry dated 22 September 2026 identifies the top shield as Board 3 and refers to testing its eighth channel.*

## 7. Prepare and document the phantom cable

The notes describe a connecting wire assembly and identify grey as channel 1 and brown as channel 8 for individual boards. They also refer to a conductor written as “pick” for “output/ground”; the intended colour and electrical function are ambiguous and must be checked physically.

An eight-channel DAC needs documented output and return connections. The phrase “8 pin wire” in the notes is insufficient to define the full connector pinout. Do not assume that colour alone identifies polarity, ground, or a return connection.

<img width="594" height="406" alt="cable-connected" src="https://github.com/user-attachments/assets/90e5f784-f2c8-4737-ba9d-95e033fa03a2" />


*Cable connection photographed during the build. Connector orientation and pin assignments still require a written pinout.*

## 8. Connect the phantom and prepare for MEG use

1. Disconnect power and check that the frame and current-dipole PCBs are secure.
2. Check the completed cable against the documented output and return mapping.
3. Connect the phantom and perform a bench check of each connected source using suitable electrical measurements.
4. Confirm the startup, idle, and shutdown output behaviour of the selected firmware before placing the phantom in the MEG setup.
5. Keep the driver electronics outside the magnetic shield. The previous phantom manual specifies placing the junction at least 1 m from the sensor array; use this as inherited setup guidance and confirm the cable routing and separation for the v3 experiment.


The earlier manual cites Oyama et al. (2015), Oyama et al. (2019), Hämäläinen et al. (1993), and Bardouille et al., *Sensors* (2024) for the dry-phantom background and earlier prototype work. Those references provide context; they do not constitute validation of this v3 assembly.

Only photographs presented as the lab's build or test setup are included here. The earlier reference image identified in the correspondence as the developer's hand and keyboard has been omitted.


The pipeline for connecting the wire is that you solder the wires to the quater board PCBs before butting them in the frame, then pass the wires through the frame and slide the PCBs in. Once all the wires are out, start twisting them. 

Next steps