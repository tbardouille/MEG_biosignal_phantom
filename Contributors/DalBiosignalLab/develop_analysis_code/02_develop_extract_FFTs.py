from supportFiles.phantom_functions import *

import mne
import matplotlib.pyplot as plot
import numpy as np
import pandas as pd
import os
import copy
import scipy.signal as ss
import scipy.stats as sstats
from sklearn.decomposition import PCA
from sklearn import linear_model
import matplotlib.pyplot as plt

from mne.evoked import combine_evoked
from mne.forward import make_forward_dipole
from mne.simulation import simulate_evoked
from mne.utils import _verbose_safe_false

import csv
from sklearn.neighbors import NearestNeighbors

###
# Phantom data analysis for scans with 13 sensors and 3 references
#	from June 26 2024, updated to not have to turn off unused channels for H. See HACK
#   from May 12 2025, updated to correct known positions for runs where the PCB was flipped
#	Using new helmet
#	Now with 4 dipoles and 4 HPI coils
#   Updated thetas: 3rd dipole was 15, now 35
#   Force bad channel exclusion in dipole fit. 


#####################
#	Updated HPI locations for the PCB board
######################
# Scans recorded 

runs = ['A', 'B', 'C', 'D', 'E', 'F', 'G'] #, 'H']
# Date of scan
date = '20261007'
# Cleaned?
cleaned = False

# File prefix
fifPre = 'phantom'
dataDir = '../processed_data'

# Make plots?
plotOK = False
# Write data?
writeOK = True

# Other (fixed) variables
outputDir = os.path.join('../processed_data', date)
supportDir = './supportFiles'

# ECD & HPI locations
hpiVal = 7.2/np.sqrt(2)	# HPI positions in cm

rho = 6.5

phis = [0, 0, 180, 180] # azimuthal angle in degrees
						# 0 degrees toward the right ear (slot C10)
						# 	and increased towards the nose (slot Nz)
thetas = [60, 15, 25, 70] # polar angle in degrees - different that wire phantom


hpiLocs = np.asarray([	[hpiVal, -hpiVal, 0],
		[hpiVal, hpiVal, 0],
		[-hpiVal, hpiVal, 0],
		[-hpiVal, -hpiVal, 0]
		])

# Other source variables used in the analysis
numSources = 16
numECDs = 12
numHPIs = 4
stimThreshold = 0.1 # voltage change threshold to catch TTL pulse
stimDuration = 120   # seconds
stimFreqs = [5.0, 5.2, 5.4, 5.6, 
			5.8, 6.0, 6.2, 6.4,
			6.6, 6.8, 7.0, 7.2,
			7.4, 7.6, 7.8, 8.0]

################################################
# Main Program

# Loop over datasets with subsets of sensors on the helmet
for r in np.arange(len(runs)):

	thisRun = runs[r]

	# Read the raw data and calculate the evoked response
	rawFif = fifPre + str(thisRun) + '_cleaned_raw.fif'
	rawFile = os.path.join(dataDir, date, rawFif)

	# Load the data
	print('Loading data: ' + rawFile)
	raw_crop = mne.io.read_raw_fif(rawFile, preload=True)
	raw_crop.drop_channels(raw_crop.info['bads'])

	# Calculate complex FFT
	fs = raw_crop.info['sfreq']
	n_samples = int(fs*stimDuration)
	dataArray = raw_crop.apply_proj().get_data()
	cropData = dataArray[:,0:n_samples]

	n_samples = cropData.shape[1]
	fft_complex = (2.0 / n_samples) * np.fft.rfft(cropData, axis=1)
	freqs = np.fft.rfftfreq(n_samples, d=1 / fs)
	fft_phasor = (2.0 / n_samples) * fft_complex
	fft_phasor[0, :] /= 2.0
	if n_samples % 2 == 0:
	    fft_phasor[-1, :] /= 2.0

	amplitude = np.abs(fft_phasor)
	phase_deg = np.angle(fft_phasor, deg=True)

	# Extract a matrix [channels x driver signal] of complex FFTs
	freqIndices = []
	for frequency_hz in stimFreqs:
		frequency_index = np.argmin(
		    np.abs(freqs - frequency_hz)
		)
		frequency_used_hz = freqs[frequency_index]
		freqIndices.append( frequency_index )

	stimFFTs = fft_complex[:,freqIndices]	# [channels x driver signal] 

	if plotOK:
		# Make a 4x4 plot where each is a scatter plot
		plotLimit = 7e-13
		fig, axes = plt.subplots(
		    nrows=4,
		    ncols=4,
		    figsize=(20, 14),
		    sharex=True,
		    sharey=True,
		)
		axes = axes.ravel()
		for i in range(16):
			ax = axes[i]
			ax.scatter(np.real(stimFFTs[:,i]), np.imag(stimFFTs[:,i]))
			ax.set_xlim(-plotLimit, plotLimit)
			ax.set_ylim(-plotLimit, plotLimit)
			ax.grid(True)
		plt.show()

	if writeOK:
		numpyFile = os.path.join(outputDir, fifPre + str(thisRun) + '_complexFFT.npy')
		print("Writing: " + numpyFile)
		np.save(numpyFile, stimFFTs)
		
