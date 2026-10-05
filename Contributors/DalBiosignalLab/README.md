---
meta:
    author: Tim Bardouille
    topic: MEG Dry Phantom
---


# MEG Biosignal Phantom v3 Build Guide

This guide documents the assembly and initial bench testing of the MEG Biosignal Phantom v3 in the Dalhousie Biosignal Laboratory. The build uses an Arduino Uno R3 and three Donders current-driver shields, each containing an eight-channel DAC7578 module. The assembled system provides up to 24 driver channels; the number of connected phantom sources depends on the head and cable configuration.

The phantom frame and current-dipole PCBs had already been assembled before the driver work described here began. This guide therefore focuses on shield assembly, address configuration, firmware installation, and connection checks.

**Documentation status:** The build notes report successful operation of the assembled driver and completion of the connecting cable. They do not include a complete cable pinout, component values, measured currents, or source-localization results. Items marked **to confirm** must be completed before this guide can serve as a fully reproducible build specification.

## 1. Design files and materials

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

Do not substitute the component list from the previous relay-based phantom driver. That manual describes an MCP4725 DAC and an eight-channel relay module, whereas this build uses DAC7578 shields.

## 2. Check the PCB revision before assembly

1. Inspect every driver PCB and record its revision.
2. Use **v1.1** for the assembly described here.
3. Check the DAC7578 module orientation against the v1.1 design before soldering.

**Important v1.0 warning:** The correspondence preserved in the build notes identifies an orientation error in the initial v1.0 driver PCB design. Installing the DAC7578 module in the normal orientation on that revision can destroy it when power is applied. The correspondence describes an inverted-module workaround, but this guide does not provide instructions for it. If the board is marked v1.0, stop and consult the documented correction in the [Donders README](https://github.com/tbardouille/MEG_biosignal_phantom/blob/main/Contributors/Donders/README.md).

![Two assembled driver shields from the lab build](images/assembled-shields.jpeg)

*Two shields assembled during this build. Confirm module orientation from the design files, rather than from a photograph alone.*

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
5. Record the actual assignments below. These entries are deliberately blank because the notes do not specify which physical board received each address.

| Physical board | Recorded I²C address | Position in stack |
| --- | --- | --- |
| Board 1 | **To confirm** | **To confirm** |
| Board 2 | **To confirm** | **To confirm** |
| Board 3 | **To confirm** | Top board in the 22 September build entry |

**Lesson from this build:** The first two shields initially used the same default address. The firmware reported them as one device, and the outputs showed the same current and frequency response. The address jumper was difficult to access after assembly, requiring rework. Configure unique addresses first to avoid this problem.

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

Do not assume a waveform, output amplitude, baud rate, or command syntax from the older driver manual. Use the selected firmware revision to determine these settings.

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

![Oscilloscope connected during driver bench testing](images/bench-test.jpeg)

*Bench testing shown in the build notes. This image documents the setup; it does not establish calibrated amplitude or frequency accuracy.*

![Three-shield stack photographed during the build](images/three-shield-stack.jpeg)

*The build entry dated 22 September 2026 identifies the top shield as Board 3 and refers to testing its eighth channel.*

## 7. Prepare and document the phantom cable

The notes describe a connecting wire assembly and identify grey as channel 1 and brown as channel 8 for individual boards. They also refer to a conductor written as “pick” for “output/ground”; the intended colour and electrical function are ambiguous and must be checked physically.

An eight-channel DAC needs documented output and return connections. The phrase “8 pin wire” in the notes is insufficient to define the full connector pinout. Do not assume that colour alone identifies polarity, ground, or a return connection.

1. Identify each driver output and its required return from the v1.1 schematic.
2. Identify every connector pin and phantom-side terminal.
3. With all power disconnected, trace each conductor using a continuity meter.
4. Check for shorts between adjacent conductors and unintended connections between sources.
5. Label both ends and add strain relief appropriate to the connector.
6. Complete the connection record before attaching the phantom.

| Shield address | Local channel label | DAC output label | Connector pin | Wire colour | Phantom source | Return connection |
| --- | --- | --- | --- | --- | --- | --- |
| **To confirm** | 1 in the notes | **To confirm** | **To confirm** | Grey in the notes | **To confirm** | **To confirm** |
| **To confirm** | 8 in the notes | **To confirm** | **To confirm** | Brown in the notes | **To confirm** | **To confirm** |

Add a row for every connected output. The Adafruit breakout labels outputs 0–7, whereas the lab notes use channels 1–8. Verify the correspondence rather than assuming the firmware uses the same numbering.

![Driver stack with the connecting cable attached](images/cable-connected.jpeg)

*Cable connection photographed during the build. Connector orientation and pin assignments still require a written pinout.*

## 8. Connect the phantom and prepare for MEG use

1. Disconnect power and check that the frame and current-dipole PCBs are secure.
2. Check the completed cable against the documented output and return mapping.
3. Connect the phantom and perform a bench check of each connected source using suitable electrical measurements.
4. Confirm the startup, idle, and shutdown output behaviour of the selected firmware before placing the phantom in the MEG setup.
5. Keep the driver electronics outside the magnetic shield. The previous phantom manual specifies placing the junction at least 1 m from the sensor array; use this as inherited setup guidance and confirm the cable routing and separation for the v3 experiment.
6. Record source positions and orientations from the actual v3 head design before localization tests.

Do not reuse the previous manual's source geometry, resistor values, nominal 17 nAm dipole strength, or 5 Hz pulse protocol without verifying their applicability to v3. Electrical operation alone does not demonstrate source-localization accuracy.

## 9. Troubleshooting

| Symptom | Checks and action |
| --- | --- |
| Two shields appear as one device | Check for duplicate I²C addresses and configure separate AD0 settings |
| Two shields respond to the same commands | Verify both addresses and firmware channel mapping; duplicate addresses caused this during the build |
| Missing `Ticker.h` during compilation | Check the required Ticker implementation and install the dependency identified by the sketch |
| DAC library compilation errors | Confirm the library name and API expected by the selected firmware revision |
| One shield is not detected | Check its address, supply, header seating, SDA/SCL continuity, and solder joints |
| A waveform appears on the wrong source | Trace the cable and check shield address, connector orientation, and channel numbering |
| AD0 is inaccessible after assembly | Rework may be necessary; configure the jumper before mounting the module in future builds |

## 10. Build record and remaining documentation

The lab notes report that two shields were assembled and tested first. After resolving their address conflict and completing the cable and phantom-end connections, a third shield was assembled using the remaining materials. The notes report successful operation, but do not provide numerical electrical measurements or MEG validation results.

Before marking the guide complete, add:

- [ ] Exact driver-design and firmware commits.
- [ ] Versioned parts list, component values, and v1.1 schematic.
- [ ] Actual address assignments and stack order.
- [ ] Arduino IDE version, exact library sources and versions, and baud rate.
- [ ] Full connector pinout, return wiring, and channel-to-source mapping.
- [ ] Head CAD/PCB revision, source geometry, and any HPI connections.
- [ ] Per-channel test settings, measured currents and frequencies, and acceptance tolerances.
- [ ] Startup and shutdown behaviour and the procedure for disabling outputs.
- [ ] MEG validation protocol and results, documented separately from bench testing.

## Sources and scope

This guide was compiled from `Phantom_v3_build_manual(1).docx` dated 3 October 2026 and the previous `PCB_phantom_build_manual(1).pdf` dated 3 October 2025. Hardware correspondence reproduced in the rough notes is treated as a historical build record. The GitHub URLs above were supplied in those notes; their current contents were not independently retrieved when preparing this guide. Check the selected repository revisions before building.

The DAC address settings and breakout output labels were checked against the [Adafruit DACx578 guide](https://learn.adafruit.com/adafruit-dac7578-8-x-channel-12-bit-i2c-dac?view=all).

The earlier manual cites Oyama et al. (2015), Oyama et al. (2019), Hämäläinen et al. (1993), and Bardouille et al., *Sensors* (2024) for the dry-phantom background and earlier prototype work. Those references provide context; they do not constitute validation of this v3 assembly.

Only photographs presented as the lab's build or test setup are included here. The earlier reference image identified in the correspondence as the developer's hand and keyboard has been omitted.
