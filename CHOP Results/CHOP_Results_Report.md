## OPM and CTF Phantom Validation at CHOP

### Background:
Advances in quantum magnetometry are increasing the global adoption of magnetoencephalography (MEG). Optically Pumped Magnetometers (OPMs) provide a cryogen-free alternative to traditional SQUID-based systems, enabling wearable and movement-tolerant MEG configurations (Tierney et al., 2019; edersen et al., 2022). Because OPMs operate in the nanotesla regime, magnetic shielding is essential. Common approaches include magnetically shielded rooms (MSRs) and portable cylindrical mu-metal shields, such as the dual-layer Mu-80 cylindrical system used in the Dalhousie Biosignal Lab (Holmes et al.,15
2022; Jodko-Władzińska et al., 2020; Bardouille et al., 2024). Validation of these systems relies on phantom-based localization testing, where known current dipoles are reconstructed via inverse modeling. Prior studies report localization accuracies in the 1–5 mm range across OPM and SQUID systems, though a universally adopted phantom standard has yet to emerge. Examples of these studies are as follows:

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

#### Theory 
The phantom contains both equivalent current dipole (ECD) and head position indicator (HPI) coils. To model the ECDs, we express the primary current density, $J_p(r)$ as:

$$
J_p(r) = Q\delta(r-r_Q),
\tag{1}
$$

where $Q$ is the current dipole moment, and $r_Q$ is the position at $Q$. From this, we can express the forward solution (as seen by the sensors) as:

$$
\mathbf{B}(\mathbf{r}) = \frac{\mu_0}{4\pi} \frac{\mathbf{Q} \times (\mathbf{r} - \mathbf{r}_Q)}{|\mathbf{r} - \mathbf{r}_Q|^3}.
\tag{2}
$$

Similarly, we can express a magnetic dipole induced by the HPI coils as the theoretical limit of closed loop with current density: 

$$
\mathbf{J}(\mathbf{r}) = \lim_{a \to 0} \left( I \sin{\theta'} \, \delta(\cos{\theta'}) \, \frac{\delta(r' - a)}{a} \right) \hat{\mathbf{e}}_\varphi
\tag{3}
$$

The induced magnetic field from this configuration, via Biot-Savart law, is:

$$
\mathbf{B}(\mathbf{r}) = \frac{\mu_0}{4\pi} \left[ \frac{3\mathbf{r} \, (\mathbf{r} \cdot \mathbf{m})}{r^5} - \frac{\mathbf{m}}{r^3} \right]
\tag{4}
$$

where $m$ is the magnetic dipole moment. In order to evaluate position and orientation of the ECDs, we optimize $Q$ and $r_Q$ to minimize least-squared error between the measured and predicted fields (Eq. 2). Likewise, the HPI coil position and orientation are given by an optimization of $m$ and $r_Q$ using Eq. 4. The solutions to this optimization are given in our MEG patient helmet's coordinate frame. We use a transformation matrix to map these coordinates directly to the phantom's frame. Localization error (LE) is calculated by finding the difference between measured and expected positions:

$$
\mathrm{LE}_i = r_i^{\text{measured}} - r_i^{\text{expected}},
\tag{5}
$$

such that the mean localization error is given by:

$$
\bar{\mathrm{LE}} = \frac{1}{N} \sum_{i} \mathrm{LE}_i .
\tag{6}
$$

We also evaluate the directional bias associated with measurements to compliment localization accuracy. To achieve this, we first measure the directional displacement $d$ for a given direction and measurement $j,i$. This is formulated as: 

$$
d_{ij} = \Delta \mathbf{r}_i \cdot \mathbf{e}_j,
\tag{7}
$$

such that the mean becomes:

$$
d_j = \frac{1}{N} \sum_i d_{ij},
\tag{8}
$$

and then our bias is calculated via:

$$
\text{bias} = \frac{d_j}{\delta d_j},
\tag{9}
$$

where $\delta d_j$ is the standard deviation of the directional displacement. These two quantities inform our measurement accuracy and validate our phantom.
#### Setup and acquisition:
 To evaluate the phantom, the device was and circuitry were manufactured (see Build Instructions.md and Circuit Layout.png) and transported via plane from Halifax to Philidelphia. Our phantom contains four head position indicator (HPI) coils and four equivalent current dipole (ECD) coils.
 At CHOP, we conducted a fixed current dipole magnitude experiment, first using a CTF SQUID MEG system and then with an OPM system in the same magnetic shielded room. The fixed magnitude was set to 17 nAm. For the CTF system, we omitted the 1000 nAm current dipole so there are 12 OPM and 11 CTF variable dipole recordings. The phantom was roughly centered within the helmet, however the phantom was not mounted to the sensor array for experiments at CHOP. Phantom position was known only via HPI localization. During the twelve repetitions of the fixed dipole magnitude experiment, the phantom was intentionally displaced slightly before each dataset was collected. 
Both MEG systems at CHOP employed full head sensor arrays with single-axis sensors. The CTF MEG system contained 276 sensors and recorded at 1200 Hz, while the OPM system contained 114 sensors and recorded at 5000 Hz. A scan consisted of applying 100 repitions of an x hz sin wave to our eight dipoles in succesion, starting with our HPI coils. 


#### OPM Data Processing 
Once acquired, OPM data were processed using MNE-Python version 1.11.0. To start, we loaded raw FIF data and extracted stimulus onsets from the driver/stim channel using peak detection (SciPy v 1.15.1) with 100-sample minimum peak-peak distance and a 0.4 s event time.. Continous noise data were cleaned by applying a 60 Hz line-noise notch filter and a 3–20 Hz band-pass filter in MNE-Python, and inspecting time courses and power spectra using MNE-Python with Matplotlib to manually identify and remove noisy or faulty channels. Before localization reference array regression (RAR) and homogeneous field correction (HFC) were applied to better filter environmental signals. Finally data were epoched around each event with applied baseline correction between -0.200 s and -0.150 s, then averaged over our 100 trials.
#### CTF Data Processing 
Similar to the OPM data, CTF scans and were preprocessed using MNE-python, although our process differed for the HPI and ECD coils. HPI scans were filtered using 3rd order synthetic gradietn compensation, and bandpasses between 1 and 20 Hz. Epochs were baselined between -0.175 s and -0.125 s and averaged to create our evoked respones. For the ECD scans, we applied zeroth order gradient compensation and temporal signal space separation (tSSS) in 10 s increments. Data were then low passed using a fourth order butterworth filter at 30 Hz. For both ECD and HPI scans, peak detection remained consistent with OPM data.

#### Localization
HPI localization followed the same procedure for both OPM and CTF datasets. Once epochs were obtained, we estimate the position and orientation of a magnetic dipole from measured MEG magnetic field data. An initial estimate of the dipole position is first defined to guide the optimization. The geometry of the MEG sensors is then constructed from the measurement information so that the physical location and orientation of each coil is known. To properly weight the measurements during fitting, a noise covariance model is used to compute a whitening transformation, which normalizes the sensor data according to the expected noise level in each channel. This "ad-hoc" whitener is computed via MNE-Covariance. 

A set of candidate dipole positions is generated within the measurement region to provide reasonable starting points for the fitting procedure. For each candidate position, the expected magnetic field pattern at the sensors is calculated using a magnetic dipole forward model (Eq. 4). The forward solution is then optimized to minimize residuals, and the best candidate location is selected.

ECD localization proceeds in a similar fashion, using Equation 4 to generate a forward model. The geometry of the ECD coil sensors is constructed using the same procedure used for the HPI coils. The unwhitened measured data is then scaled to prevent floating-point errors during the least-squares optimization. Using three time points (0 ± 1 ms), the dipole moment is calculated for the candidate position, with the moment constrained to remain the same across all time points. Residuals are then computed by evaluating the difference between the expected and simulated lead fields. A new dipole position is subsequently searched using a nonlinear least-squares optimization implemented with SciPy. The optimization is initialized using the expected ECD positions expressed in the MNE coordinate frame. After the fitting procedure is complete, the results are rescaled to undo the earlier data scaling.

Resulting HPI locations are then transformed into the phantom's coordinate frame using point-cloud alignment with the known coil positions. This same transformation matrix is then applied to ECD positions, giving us our localizations. 

### Results:

#### OPM Localization 


#### CTF Localization

Figure x shows an example scan 




