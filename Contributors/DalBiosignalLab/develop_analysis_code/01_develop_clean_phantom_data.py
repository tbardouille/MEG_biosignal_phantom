from supportFiles.phantom_functions import *

import mne
import matplotlib.pyplot as plot
import numpy as np
import pandas as pd
import os
import copy
import scipy.signal as ss
import scipy.stats as sstats
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
dataDir = '../raw_data'

# Make plots?
plotOK = True
# Write data?
writeOK = True

# Other (fixed) variables
outputDir = os.path.join('../processed_data', date)
supportDir = './supportFiles'
digName = 'Default Sensor locations - AllSensors_48mm_fixed.xls' 

shcOrder=1
windowDuration = 4  # seconds
n_fft = 2000

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

l_freq=1
h_freq=20

# New subsets for Helmet v2 (missing 10 slots as compared to v1 helmet)
channelSubsets = [ 	['Fpz', 'AFpz', 'AFz', 						# A
						'AFp3', 'Fp1', 'AF1', 'AF3', 'AF5', 
						'AFp4', 'Fp2', 'AF2', 'AF4', 'AF6'],
					['Fz', 										# B
						'AF7', 'F1', 'F3', 'F5', 'F7', 'F9',
						'AF8', 'F2', 'F4', 'F6', 'F8', 'F10'],
					['FCz', 									# C
						'FC1', 'FC3', 'FC5', 'FC7', 'FC9', 'FT7',
						'FC2', 'FC4', 'FC6', 'FC8', 'FC10', 'FT8'],
					['CPz', 									# D
						'C1',  'C3', 'C5', 'C7', 'CP1', 'CP3', 
						'C2', 'C4', 'C6', 'C8', 'CP2', 'CP4'],	
					['Pz', 										# E 
						'CP5', 'CP7', 'CP9', 'TP7', 'P1', 'P3', 
						'CP6', 'CP8', 'CP10', 'TP8', 'P2', 'P4'], 
					['POz', 									# F 
						'P5', 'P7', 'P9', 'P11', 'PO1', 'PO3', 
						'P6', 'P8', 'P10', 'P12', 'PO2', 'PO4'],
					['Oz', 										# G 
						'PO5', 'PO7', 'PO9', 'O1', 'O5', 'O9', 
						'PO6', 'PO8', 'PO10', 'O2', 'O6', 'O10'],	
					['OIz', 'OIhz', 'Iz',]						# H 
				]

################################################
# Main Program

# Make the ouput dataset if it doesn't exist
if os.path.exists(outputDir)==False:
	os.makedirs(outputDir)

# Loop over datasets with subsets of sensors on the helmet
for r in np.arange(len(runs)):

	thisRun = runs[r]
	thisSubset = channelSubsets[r]

	# Read sensor info used in the acquisiion (default depth)
	#	and place positions in an array
	locArray, sensorNames = getSensorLocations(supportDir, digName)

	# Read the raw data and calculate the evoked response
	rawFif = fifPre + str(thisRun) + '_raw.fif'
	rawFile = os.path.join(dataDir, date, rawFif)

	# Load the data
	raw = mne.io.read_raw_fif(rawFile, preload=True)

	# Get MEG channels only
	raw_meg = raw.copy().pick('mag')
		
	# Extract only the data when the current is being driven
	stimData = raw.get_data()[-1,:]
	stimDiff = np.diff(stimData)
	stimHigh = np.where(stimDiff > stimThreshold)[0]
	stimOn = stimHigh[0]
	# Crop data to start at the stimulus onset
	onTime = raw.times[stimOn]
	offTime = onTime + stimDuration
	raw_meg = raw_meg.copy().crop(onTime, offTime)

	# Get indices for sensors and references
	opmIndices = mne.channel_indices_by_type(raw_meg.info)['mag']
	numChannels = len(opmIndices)
	numSensors = numChannels-3
	sensorIndices = opmIndices[0:numSensors]
	referenceIndices = opmIndices[-3::]

	# Update sensor names and locations
	raw_loc = updateSensorNamesAndLocations(raw_meg.copy(), thisRun, thisSubset, locArray, sensorNames)

	# Set the last three sensors as "bad" so they are:
	#	automatically excluded from HFC
	#	manually excluded from PSD
	#	included (but irrelevant) for reference array regression
	refChannels = raw_loc.info['ch_names'][-3::]
	raw_loc.info['bads'].extend(refChannels)

	# Filter and downsample
	raw_filt = raw_loc.copy()
	raw_filt = raw_filt.notch_filter([60, 120, 180])
	raw_filt = raw_filt.filter(l_freq=l_freq, h_freq=h_freq)

	# DC offset and detrend
	raw_detrend = windowData(detrendData(raw_filt.copy(), opmIndices), opmIndices, windowDuration)

	# Reference array regression 
	raw_regressed = referenceArrayRegression(raw_detrend.copy(), opmIndices, sensorIndices, referenceIndices)

	# Homogenous field compensation (HFC)
	raw_hfc = raw_regressed.copy()
	projs = mne.preprocessing.compute_proj_hfc(raw_hfc.info, order=shcOrder)
	raw_hfc.add_proj(projs)
	raw_hfcApplied = raw_hfc.copy().apply_proj(verbose="error")

	if writeOK:
		outFif = fifPre + str(thisRun) + '_cleaned_raw.fif'
		outFile = os.path.join(outputDir, outFif)
		print('Writing: ' + outFile)
		raw_hfc.save(outFile, overwrite=True)

	

