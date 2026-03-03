## OPM and CTF Phantom Validation at CHOP

### Background:
Advances in quantum magnetometry are increasing the global adoption of magnetoencephalography (MEG). Optically Pumped Magnetometers (OPMs) provide a cryogen-free alternative to traditional SQUID-based systems, enabling wearable and movement-tolerant MEG configurations. Because OPMs operate in the nanotesla regime, magnetic shielding is essential. Common approaches include magnetically shielded rooms (MSRs) and portable cylindrical mu-metal shields, such as the dual-layer Mu-80 cylindrical system used in the Dalhousie Biosignal Lab. Validation of these systems relies on phantom-based localization testing, where known current dipoles are reconstructed via inverse modeling. Prior studies report localization accuracies in the 1–5 mm range across OPM and SQUID systems, though a universally adopted phantom standard has yet to emerge. Examples of these studies are as follows:

| Study | Study Type | Reported LE | Link |
|-------|------------|------------|------|
| Boto et al., 2022 | Wet phantom, tri-axial OPM | ~5 mm | https://doi.org/10.1016/j.neuroimage.2022.119027 |
| Bardouille et al., 2024 | Dry phantom, cylindrical OPM shield | 3–5 mm | https://doi.org/10.3390/s24113503 |
| Tanaka et al., 2024 | SQUID dry phantom evaluation | 1–5 mm | https://doi.org/10.3390/s24186044 |
| Cao et al., 2023 | Realistic 3-layer OPM head phantom | ~1–5 mm | https://doi.org/10.1016/j.compbiomed.2023.107318 |
| Oyama & Zaatiti, 2025 | Phantom comparison: SQUID vs OPM | 1–5 mm  | https://doi.org/10.3390/s25072063 |
| Leahy et al., 1998 | Human skull phantom (MEG/EEG) | ~2–5 mm | https://doi.org/10.1016/S0013-4694(98)00057-1 |
| Bastola et al., 2024 | MEG-EEG phantom optimization | 4-5 mm (MEG ONLY)| https://doi.org/10.3390/bioengineering11090897 |



 This work aims to design and validate a cost-effective dry phantom capable of achieving <3 mm localization accuracy across both cylindrical OPM and SQUID-MEG systems, including evaluation within the Children's Hosptital of Philidelphia (CHOP) OPM nad CTF-MEG systems. 

 ### Methods:

#### Setup and acquisition:
 To evaluate the phantom, the device was and circuitry were manufactured (see Build Instructions.md and Circuit Layout.png) and transported via plane from Halifax to Philidelphia.
 At CHOP, we conducted a fixed current dipole magnitude experiment, first using a CTF SQUID MEG system and then with an OPM system in the same magnetic shielded room. The fixed magnitude was set to 17 nAm. For the CTF system, we omitted the 1000 nAm current dipole so there are 12 OPM and 11 CTF variable dipole recordings. The phantom was roughly centered within the helmet, however the phantom was not mounted to the sensor array for experiments at CHOP. Phantom position was known only via HPI localization. During the twelve repetitions of the fixed dipole magnitude experiment, the phantom was intentionally displaced slightly before each dataset was collected. 
Both MEG systems at CHOP employed full head sensor arrays with single-axis sensors. The CTF MEG system contained 276 sensors and recorded at 1200 Hz, while the OPM system contained 114 sensors and recorded at 5000 Hz.

#### OPM Data Processing and Dipole Fitting:

#### CTF Data Processing and Dipole Fitting:

### Results:





