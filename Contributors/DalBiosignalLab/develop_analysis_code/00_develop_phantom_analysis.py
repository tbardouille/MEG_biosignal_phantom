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
if cleaned:
	fifPre = 'cleaned_phantom'
	dataDir = '../processed_data'
else: 
	fifPre = 'phantom'
	dataDir = '../raw_data'

# Make plots?
plotOK = True
# Write data?
writeOK = False

# Other (fixed) variables
outputDir = '../results/' + date
supportDir = '../supportFiles'
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

if int(date) < 20250000:
	phis = [180, 180, 0, 0] # azimuthal angle in degrees

	hpiLocs = np.asarray([	[hpiVal, hpiVal, 0],
			[hpiVal, -hpiVal, 0],
			[-hpiVal, -hpiVal, 0],
			[-hpiVal, hpiVal, 0]
		])

			


def xyz2rpt(xyz):
	'''
	in: xyz - [x,y,z]
	out: rpt - [r,phi,theta]
	'''
	x,y,z = xyz
	r = np.sqrt(x**2+y**2+z**2)
	rxy = np.sqrt(x**2+y**2)
	theta = np.arctan(rxy/z)*180/np.pi
	phi = np.arctan2(y,x)*180/np.pi

	# Restrict theta to [0, 180]
	if theta < 0:
		theta += 180   # if the polar angle is negative, flip the sign by rotating the azimuthal angle by 180 degrees

	# Restrict phi to [0, 360]
	if phi < 0:
		phi += 360
	elif phi > 360:
		phi -= 360

	return np.array([r, phi, theta])


def rpt2xyz(rpt):
    '''
    in: rpt - [r,phi,theta]
    out: xyz - [x,y,z]
    '''
    r, phi, theta = rpt
    phi = phi*np.pi/180
    theta = theta*np.pi/180
   
    x=r*np.sin(theta)*np.cos(phi)
    y=r*np.sin(theta)*np.sin(phi)
    z=r*np.cos(theta)
    return np.array([x,y,z])


ecdLocs_rpt = np.asarray([	[rho, phis[0], thetas[0]],
							[rho, phis[1], thetas[1]],
						  	[rho, phis[2], thetas[2]],
						    [rho, phis[3], thetas[3]]
							])

ecdLocs_xyz = np.asarray([  rpt2xyz(ecdLocs_rpt[0]).tolist(),
						 	rpt2xyz(ecdLocs_rpt[1]).tolist(),
							rpt2xyz(ecdLocs_rpt[2]).tolist(),
							rpt2xyz(ecdLocs_rpt[3]).tolist()
							])

# adjust the ECD locations for runs where the PCB was flipped
if int(date) < 20250000:
	ecdLocs_xyz[0][1] += -0.16
	ecdLocs_xyz[1][1] += -0.16
	ecdLocs_xyz[2][1] += -0.16
	ecdLocs_xyz[3][1] += -0.16
##############################################################################################

	ecdLocs_rpt = np.asarray([  xyz2rpt(ecdLocs_xyz[0]).tolist(),
						 	xyz2rpt(ecdLocs_xyz[1]).tolist(),
							xyz2rpt(ecdLocs_xyz[2]).tolist(),
							xyz2rpt(ecdLocs_xyz[3]).tolist()
							])






# Other source variables used in the analysis
numSources = 8
numECDs = 4
numHPIs = 4

numActivations = 100
epochStart = -0.200
epochEnd = 0.200
baselineStart = -0.150
baselineEnd = -0.100
HPIFitSample = 200 		# sample in the evoked data for HPI (mag dip) fitting
						#	should be in the middle of the epoch
ECDFitSample = 5 		# sample in the evoked data for ECD fitting

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
# Functions

def getSensorLocations(supportDir, digName):
	# Get file with default sensor locations for this sensor layout
	digDf = pd.read_excel(os.path.join(supportDir, digName))

	# Make the array to set sensor locations
	locColumns = ['sensor_x', 'sensor_y', 'sensor_z', 'ex_i',
	       'ex_j', 'ex_k', 'ey_i', 'ey_j', 'ey_k', 'ez_i', 'ez_j', 'ez_k']
	locArray = np.asarray(digDf.loc[:,locColumns])

	sensorNames = digDf['Sensor Names'].to_list()

	return locArray, sensorNames

def updateSensorNamesAndLocations(raw, thisRun, channelSubset, locArray, sensorNames):

	# Determine the relevant indices for channels of interest
	channelSubsetIndex = [sensorNames.index(i) for i in channelSubset]
	numChannels = len(channelSubsetIndex)

	# Take only relevant locations
	locSubArray = locArray[channelSubsetIndex,:]

	# Replace locations in raw.info
	newRaw = raw.copy()
	offsetIndex = 0
	for c in np.arange(numChannels):
	    channelIndex = c+offsetIndex
	    newRaw.info['chs'][channelIndex]['loc'] = locSubArray[c,:]

	# Rename channels based on the dataset (to avoid duplicate sensor names in the combined evoked)
	numSensors = len(channelSubset)
	channelNames = newRaw.info['ch_names'][offsetIndex:numSensors]
	ctr = 0
	nameDict = {}
	for ch in channelNames:
		nameDict[ch] = channelSubset[ctr]
		ctr += 1
	newRaw.rename_channels(nameDict)

	return newRaw

def referenceArrayRegression(raw_filter, opmChannels, sensorChannels, refChannels):

	# Window data (1 second cosine) to clean out high-pass edge effects
	opmData = raw_filter.get_data()[opmChannels]

	# Remove signals related to reference signals via regression
	sensorData = opmData[sensorChannels,:]
	referenceData = opmData[refChannels,:]

	numSensors = len(sensorChannels)
	regressData = copy.copy(sensorData)
	for i in np.arange(numSensors):
		# Put data into a pandas dataframe
		data = {'sensor': sensorData[i,:],
				'Xref': referenceData[0,:],
				'Yref': referenceData[1,:],
				'Zref': referenceData[2,:],
				}
		df = pd.DataFrame(data)
		x = df[['Xref','Yref', 'Zref']]
		y = df['sensor']
		# Run multi-variable regression
		regr = linear_model.LinearRegression()
		regr.fit(x, y)
		# Extract cleaned sensor data 
		regressData[i,:] = sensorData[i,:] - regr.coef_[0]*referenceData[0,:] - regr.coef_[1]*referenceData[1,:] - regr.coef_[2]*referenceData[2,:]

	# Put cleaned data into a raw_regress object
	allData = raw_filter.get_data()
	allData[sensorChannels,:] = regressData
	raw_regressed = mne.io.RawArray(allData, raw_filter.info)

	return raw_regressed

def detrendData(raw, opmChannels):

	# Linear regression to baseline correct and detrend
	opmData = raw.copy().pick('mag').get_data()
	opmDataBaseCorr = copy.copy(opmData)
	for i in np.arange(opmData.shape[0]):
		result = sstats.linregress(raw.times,opmData[i,:])
		modelFit = result.intercept + result.slope*raw.times
		opmDataBaseCorr[i,:] = opmData[i,:] - modelFit

	# Put detrended data into a raw object
	allData = raw.get_data()
	allData[opmChannels,:] = opmDataBaseCorr
	raw_detrend = mne.io.RawArray(allData, raw.info)

	return raw_detrend

def windowData(raw, opmChannels, winDur):

	# Window data (1 second cosine) to clean out high-pass edge effects
	opmData = raw.copy().pick('mag').get_data()
	numSamples = opmData.shape[1]
	numChannels = opmData.shape[0]
	fs = raw.info['sfreq']
	cosTimes =  np.arange(winDur*fs)/fs
	cosWin = np.expand_dims(-0.5*np.cos(2*np.pi*0.5*cosTimes/winDur)+0.5,0)	# half a cosine
	middleWin = np.ones((1,numSamples-2*len(cosTimes)))
	fullWindow = np.tile(np.hstack((cosWin, middleWin, cosWin[:,::-1])), (numChannels,1))
	windowedData = opmData*fullWindow

	# Put detrended data into a raw object
	allData = raw.get_data()
	allData[opmChannels,:] = windowedData
	raw_win = mne.io.RawArray(allData, raw.info)

	return raw_win

def getEvents(raw, voltageThreshold):

	# Get the stim channel, which has different voltage values for each interval type in the experiment
	stimChan = mne.channel_indices_by_type(raw.info)['stim'][0]
	stimData = raw.get_data()[stimChan,:]
		
	# Using the phantom driver signal to get events
	peakIndex = ss.find_peaks(stimData, height=voltageThreshold, distance=100)[0]
	numTrials = len(peakIndex)
	print('There are ' + str(numTrials) + ' trials.')

	# Make a list of the onset time of each stimulus
	events = np.vstack((peakIndex, np.zeros(numTrials)))
	events = np.vstack((events, np.ones(numTrials))).T.astype(int)

	return events	

def calcEvoked(raw, events, project, numSources, numActivations, epochStart, epochEnd, baselineStart, baselineEnd):

	# Split the raw data into epochs per source
	# 	Epoch and average 
	evokeds = []
	for s in np.arange(numSources):
		firstEvent = s*numActivations
		lastEvent = (s+1)*numActivations
		epochs = mne.Epochs(raw, events[firstEvent:lastEvent,:], tmin=epochStart, tmax=epochEnd, 
			baseline=(baselineStart,baselineEnd), preload=True, proj=project)
		evoked = epochs.average().apply_baseline((baselineStart,baselineEnd))
		# Drop the last three channels (reference array)
		evoked.drop_channels(evoked.info['ch_names'][-3:])
		evokeds.append(evoked)

	return evokeds

def flip_sensors(raw, sens1Ind, sens2Ind): # Not called in this script

	data = raw.get_data()
	newData = copy.copy(data)
	newData[sens1Ind,:] = data[sens2Ind,:]
	newData[sens2Ind,:] = data[sens1Ind,:]
	newRaw = mne.io.RawArray(newData, raw.info)

	return newRaw

def combineProjection(combinedEvoked, startInd, stopInd):

	allNames = []
	allData = [] 
	for p in np.arange(startInd, stopInd):
		thisName = combinedEvoked.info['projs'][p]['data']['col_names']
		allNames.append(thisName)
		thisData = combinedEvoked.info['projs'][p]['data']['data'][0]
		allData.append(thisData)
	col_names = [x for xs in allNames for x in xs]
	data = [x for xs in allData for x in xs]
	ncol = len(data)
	newProj1={}
	newProj1['data']={}
	newProj1['data']['col_names'] = col_names
	newProj1['data']['row_names'] = None
	newProj1['data']['data'] = np.asarray([data])
	newProj1['data']['ncol'] = ncol
	newProj1['data']['nrow'] = 1
	newProj1['desc'] = 'HFC: l=1 m=0'
	newProj1['kind'] = 1
	newProj1['active'] = False
	proj1 = mne.Projection(data=newProj1['data'], desc=newProj1['desc'], kind=newProj1['kind'], active=newProj1['active'], explained_var=None)

	return proj1

def combineEvokedDatasets(allEvokeds):
	
	# Combine all channels into one list of evoked variable (one evoked per source_)
	combinedEvokeds = allEvokeds[0].copy()
	for evs in allEvokeds[1::]:
	    for s in np.arange(numSources):
	        combinedEvokeds[s].add_channels([evs[s]])

	# Combine HFC projectors
	if len(allEvokeds[0][0].info['projs'])>0:
		numRuns = len(allEvokeds)
		proj1 = combineProjection(combinedEvokeds[0], 0, numRuns)
		proj2 = combineProjection(combinedEvokeds[0], numRuns, numRuns*2)
		proj3 = combineProjection(combinedEvokeds[0], numRuns*2, numRuns*3)

	# Write new projectors to the evoked data
	newCombinedEvokeds = []
	for ev in combinedEvokeds:
		if len(allEvokeds[0][0].info['projs'])>0:
			newEv = ev.copy().add_proj([proj1, proj2, proj3], remove_existing=True, verbose=False).apply_proj(verbose="error")
		else:
			newEv = ev.copy()
		newCombinedEvokeds.append(newEv)

	return newCombinedEvokeds

def plot_raw_data(raw1, raw2, raw3, raw4):
	fig, ax = plt.subplots(2,4)

	fmax = 50
	yRange = [10,1e4]
	thisRaw = raw1.copy()
	i=0
	ax[0,i].plot(thisRaw.times, thisRaw.copy().pick('mag').get_data().T)
	ax[0,i].set_title('BandPass + Notch')
	PSD = thisRaw.compute_psd(n_fft=2000, exclude='bads')
	PSD.plot(axes=ax[1,i], dB=False, show=False, amplitude=True)
	ax[1,i].set_xlim([0,fmax])
	ax[1,i].set_yscale('log')
	ax[1,i].set_ylim(yRange)

	thisRaw = raw2.copy()
	i=1
	ax[0,i].plot(thisRaw.times, thisRaw.copy().pick('mag').get_data().T)
	ax[0,i].set_title('Detrended')
	PSD = thisRaw.compute_psd(n_fft=2000, exclude='bads')
	PSD.plot(axes=ax[1,i], dB=False, show=False, amplitude=True)
	ax[1,i].set_xlim([0,fmax])
	ax[1,i].set_yscale('log')
	ax[1,i].set_ylim(yRange)

	thisRaw = raw3.copy()
	i=2
	ax[0,i].plot(thisRaw.times, thisRaw.copy().pick('mag').get_data().T)
	ax[0,i].set_title('HFC')
	PSD = thisRaw.compute_psd(n_fft=2000, exclude='bads')
	PSD.plot(axes=ax[1,i], dB=False, show=False, amplitude=True)
	ax[1,i].set_xlim([0,fmax])
	ax[1,i].set_yscale('log')
	ax[1,i].set_ylim(yRange)

	thisRaw = raw4.copy()
	i=3
	ax[0,i].plot(thisRaw.times, thisRaw.copy().pick('mag').get_data().T)
	ax[0,i].set_title('Regressed')
	PSD = thisRaw.compute_psd(n_fft=2000, exclude='bads')
	PSD.plot(axes=ax[1,i], dB=False, show=False, amplitude=True)
	ax[1,i].set_xlim([0,fmax])
	ax[1,i].set_yscale('log')
	ax[1,i].set_ylim(yRange)

	plt.show()

def dipoleFitEvoked(supportDir, combinedEvoked):

	################
	# Set up source inside a sphere
	bemSphere = mne.make_sphere_model(r0=(0,0,0.0), head_radius=0.08, info=combinedEvoked.info)

	cov = mne.make_ad_hoc_cov(combinedEvoked.info)

	# Identity transformation between head and mri space
	trans2 = np.eye(4)
	trans2 = mne.transforms.Transform('head', 'mri', trans=trans2) 

	# Do the dipole fitting
	dip_opm, _ = mne.fit_dipole(combinedEvoked.copy().crop(-0.005,0.005), cov, bemSphere, trans2, verbose=False)

	# Extract the position at the peak of the 5 Hz signal (50 ms) in cm
	pos = dip_opm.pos[5,:]*100

	return pos, dip_opm

def magDipoleFit(B, info):

	x0 = np.asarray([.065, .065, .02])	# metres ?
	too_close = 'raise'
	safe_false = _verbose_safe_false()

	# Exclude bads

	picks_meg = mne.pick_types(info, meg=True, eeg=False, stim=False, eog=False, exclude='bads')
	chs_meg = [info['chs'][p] for p in picks_meg]


	meg_coils = mne.chpi._concatenate_coils(
	    mne.chpi._create_meg_coils(chs_meg, 'accurate')
	)


	cov = mne.cov.make_ad_hoc_cov(info, verbose=safe_false)



	whitener, _ = mne.cov.compute_whitener(cov, info, picks=picks_meg, verbose=safe_false)
	
	

	R = np.linalg.norm(meg_coils[0], axis=1).min()
	guesses = mne.chpi._make_guesses(
	    dict(R=R, r0=np.zeros(3)), 0.01, 0.0, 0.005, verbose=safe_false
	)[0]["rr"]

	fwd = mne.chpi._magnetic_dipole_field_vec(guesses, meg_coils, too_close)
	fwd = np.dot(fwd, whitener.T)
	fwd.shape = (guesses.shape[0], 3, -1)
	fwd = np.linalg.svd(fwd, full_matrices=False)[2]
	guesses = dict(rr=guesses, whitened_fwd_svd=fwd)

	

	x, gof, moment = mne.chpi._fit_magnetic_dipole(B, x0, too_close, whitener, meg_coils, guesses)

	return x, gof, moment 

def plot_topos(evoked, pred_evoked, diff_evoked, dsNum, dipNum, colourRange):

	# remember to create a subplot for the colorbar
	fig, axes = plt.subplots(
	    nrows=1,
	    ncols=4,
	    figsize=[10.0, 3.4],
	    gridspec_kw=dict(width_ratios=[1, 1, 1, 0.1], top=0.85),
	    layout="constrained",
	)
	plot_params = dict(times=[0], ch_type="mag", outlines="head", colorbar=False, vlim=(-colourRange,colourRange))

	# first plot the topography at the time of the best fitting (single) dipole
	evoked.plot_topomap(time_format="Measured field", axes=axes[0], **plot_params)

	# then plot the predicted field
	pred_evoked.plot_topomap(time_format="Predicted field", axes=axes[1], **plot_params)

	# Now add in subtraction plot
	plot_params["colorbar"] = True
	diff_evoked.plot_topomap(time_format="Difference", axes=axes[2:], **plot_params)
	fig.suptitle(
	    "Dipole Fit "
	    "for source {:d} in dataset {:d}".format(dipNum, dsNum),
	    fontsize=16,
	)
	return fig

def xyz2rpt(xyz):
	'''
	in: xyz - [x,y,z]
	out: rpt - [r,phi,theta]
	'''
	x,y,z = xyz
	r = np.sqrt(x**2+y**2+z**2)
	rxy = np.sqrt(x**2+y**2)
	theta = np.arctan(rxy/z)*180/np.pi
	phi = np.arctan2(y,x)*180/np.pi

	# Restrict theta to [0, 180]
	if theta < 0:
		theta += 180   # if the polar angle is negative, flip the sign by rotating the azimuthal angle by 180 degrees

	# Restrict phi to [0, 360]
	if phi < 0:
		phi += 360
	elif phi > 360:
		phi -= 360

	return np.array([r,phi,theta])


def rpt2xyz(rpt):
    '''
    in: rpt - [r,phi,theta]
    out: xyz - [x,y,z]
    '''
    r, phi, theta = rpt
    phi = phi*np.pi/180
    theta = theta*np.pi/180
   
    x=r*np.sin(theta)*np.cos(phi)
    y=r*np.sin(theta)*np.sin(phi)
    z=r*np.cos(theta)
    return np.array([x,y,z])

def ampSpec(raw, n_fft):
	# Amplitude spectra 
	PSDs = raw.compute_psd(n_fft=n_fft, exclude='bads')
	ampSpecData = np.sqrt( PSDs.get_data() ) * 1e15 # in fT
	freq = PSDs.freqs

	return ampSpecData, freq

################################################
# Main Program

# Loop over datasets with subsets of sensors on the helmet
allEvokeds_det = []
allEvokeds_hfc = []
allEvokeds_regr = []
ampSpec_filts = []
ampSpec_hfcs = []

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
	
	# HACK! Drop unneeded channels from phantomH
	if raw.info.ch_names[0][10] == 'O' and r==7:		# in case open loop
		if len(raw.info.ch_names) > 7:						# if sensors 4-13 weren't turned off for H, drop them
			raw.drop_channels(['FL0104-BZ_OL', 
				'FL0105-BZ_OL', 
				'FL0106-BZ_OL', 
				'FL0107-BZ_OL', 
				'FL0108-BZ_OL', 
				'FL0109-BZ_OL', 
				'FL0110-BZ_OL', 
				'FL0111-BZ_OL', 
				'FL0112-BZ_OL', 
				'FL0113-BZ_OL'])
	elif r==7:
		if len(raw.info.ch_names) > 7:				      # if sensors 4-13 weren't turned off for H, drop them	
			raw.drop_channels(['FL0104-BZ_CL', 
				'FL0105-BZ_CL', 
				'FL0106-BZ_CL', 
				'FL0107-BZ_CL', 
				'FL0108-BZ_CL', 
				'FL0109-BZ_CL', 
				'FL0110-BZ_CL', 
				'FL0111-BZ_CL', 
				'FL0112-BZ_CL', 
				'FL0113-BZ_CL'])

	raw_meg = raw.copy().pick('mag')
		
	# Extract phantom peak activations timing
	events = getEvents(raw, 1)

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

	# Grab the amplitude spectrum
	ampSpec_filt, freq = ampSpec(raw_detrend.copy(), n_fft)

	########## Combining channels 
	
	# Reference array regression 
	raw_regressed = referenceArrayRegression(raw_detrend.copy(), opmIndices, sensorIndices, referenceIndices)

	# Homogenous field compensation (HFC)
	raw_hfc = raw_regressed.copy()
	projs = mne.preprocessing.compute_proj_hfc(raw_hfc.info, order=shcOrder)
	raw_hfc.add_proj(projs)
	raw_hfcApplied = raw_hfc.copy().apply_proj(verbose="error")

	# Grab the amplitude spectrum
	ampSpec_hfc, freq = ampSpec(raw_hfcApplied, n_fft)
	
	# Calculate the evoked responses (HFC projection is carried thru but not necessarily applied)
	project = False
	evokeds_hfc = calcEvoked(raw_hfc, events, project, numSources, numActivations, epochStart, epochEnd, baselineStart, baselineEnd)
	evokeds_regr = calcEvoked(raw_regressed, events, project, numSources, numActivations, epochStart, epochEnd, baselineStart, baselineEnd)
	evokeds_det = calcEvoked(raw_detrend, events, project, numSources, numActivations, epochStart, epochEnd, baselineStart, baselineEnd)

	ampSpec_filts.append ( ampSpec_filt )
	ampSpec_hfcs.append ( ampSpec_hfc )
	allEvokeds_hfc.append( evokeds_hfc )
	allEvokeds_regr.append( evokeds_regr )
	allEvokeds_det.append( evokeds_det )

# Stack all amplitude spectra into one array
for r in np.arange(len(runs)):
	if r==0:
		ampSpec_filt = copy.copy(ampSpec_filts[r])
		ampSpec_hfc = copy.copy(ampSpec_hfcs[r])
	else:
		ampSpec_filt = np.vstack((ampSpec_filt, ampSpec_filts[r]))
		ampSpec_hfc = np.vstack((ampSpec_hfc, ampSpec_hfcs[r]))
ampSpecData = np.asarray( [ampSpec_filt, ampSpec_hfc])
ampSpec_mean = np.mean(ampSpecData, axis=1)

# Shielding Factor
shieldFactorSpectrum = 20*np.log10(ampSpecData[0,:,:]/ampSpecData[1,:,:])
shieldFactor_mean = np.mean(shieldFactorSpectrum, axis=0)

# Combine consecutive evokeds datasets
combinedEvokeds_hfc = combineEvokedDatasets(allEvokeds_hfc)
combinedEvokeds_regr = combineEvokedDatasets(allEvokeds_regr)
combinedEvokeds_det = combineEvokedDatasets(allEvokeds_det)

# Save averaged MEG data
if writeOK:
	for s in np.arange(numSources):
		outFif = os.path.join(outputDir, fifPre + 'source' + str(s+1) + '-ave.fif')
		combinedEvokeds_hfc[s].save(outFif, overwrite=True)

# Fit one magnetic dipole for each HPI source 
HPIFitData = []
ctr = 0
for s in np.arange(numHPIs)+numECDs:

	# Fit magnetic dipole (in device coordinate frame)
	good_data = mne.pick_types(combinedEvokeds_hfc[s].info, meg=True, exclude='bads')
	B_hpi = combinedEvokeds_hfc[s].data[good_data,HPIFitSample].T
	x, gof, moment = magDipoleFit(B_hpi, combinedEvokeds_hfc[s].info)
	
	fitData = {}
	fitData['pos'] = x*100			# cm
	fitData['gof'] = gof*100		# %
	fitData['amplitude'] = moment

	fitData['knownPosition_xyz'] = hpiLocs[ctr]
	fitData['knownPosition_rpt'] = xyz2rpt(hpiLocs[ctr])
	fitData['deltaR'] = fitData['pos'] - fitData['knownPosition_xyz']
	fitData['LEmag'] = np.sqrt(np.sum(fitData['deltaR']*fitData['deltaR']))
	fitData['rpt'] = xyz2rpt(fitData['pos'])

	HPIFitData.append(fitData)

	ctr = ctr + 1

####################################  Iterative Closest Point #####################################################
def align_point_clouds(source, target, max_iterations=100, tolerance=0.001):
    """
    Rigidly aligns two point clouds using the Iterative Closest Point (ICP) algorithm.

    Args:
        source (np.ndarray): Source point cloud (N x 3).
        target (np.ndarray): Target point cloud (M x 3).
        max_iterations (int): Maximum number of ICP iterations.
        tolerance (float): Tolerance for convergence.

    Returns:
        tuple: A tuple containing the aligned source point cloud and the transformation matrix.
    """
    src = source.copy()
    transformation_matrix = np.eye(4)

    for i in range(max_iterations):
        # Find nearest neighbors
        knn = NearestNeighbors(n_neighbors=1, algorithm='auto').fit(target)
        distances, indices = knn.kneighbors(src)

        # Compute the transformation
        T = compute_transformation(src, target[indices.flatten()])

        # Update the source point cloud and transformation matrix
        src = apply_transformation(src, T)
        transformation_matrix = T @ transformation_matrix

        # Check for convergence
        if np.mean(distances) < tolerance:
            break

    return src, transformation_matrix


def compute_transformation(source, target):
    """
    Computes the transformation matrix between two point clouds.

    Args:
        source (np.ndarray): Source point cloud (N x 3).
        target (np.ndarray): Target point cloud (N x 3).

    Returns:
        np.ndarray: The 4x4 transformation matrix.
    """
    # Center the point clouds
    source_mean = np.mean(source, axis=0)
    target_mean = np.mean(target, axis=0)
    source_centered = source - source_mean
    target_centered = target - target_mean

    # Compute the covariance matrix
    H = source_centered.T @ target_centered

    # Compute the SVD
    U, S, Vt = np.linalg.svd(H)

    # Compute the rotation matrix
    R = Vt.T @ U.T

    # Correct rotation matrix for possible reflection
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T

    # Compute the translation vector
    t = target_mean - R @ source_mean

    # Create the transformation matrix
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t

    return T

def apply_transformation(points, transformation_matrix):
    """
    Applies a transformation matrix to a point cloud.

    Args:
        points (np.ndarray): Point cloud (N x 3).
        transformation_matrix (np.ndarray): 4x4 transformation matrix.

    Returns:
        np.ndarray: Transformed point cloud (N x 3).
    """
    # Convert points to homogeneous coordinates
    homogeneous_points = np.hstack((points, np.ones((points.shape[0], 1))))

    # Apply the transformation
    transformed_points = (transformation_matrix @ homogeneous_points.T).T

    # Return the transformed points
    return transformed_points[:, :3]

# Step 5 froom steps v14
HPImeas = np.asarray([HPIFitData[0]['pos'],HPIFitData[1]['pos'],
	HPIFitData[2]['pos'],HPIFitData[3]['pos']])

# Align the point clouds
aligned_cloud, transformation_matrix = align_point_clouds(HPImeas, hpiLocs)
# Add positions in phantom coordinate frame to dictionary
for i in np.arange(4):
	HPIFitData[i]['pos_prime'] = aligned_cloud[i,:]
# Save the variable

if not os.path.exists('../proc_data'):
	os.makedirs('../proc_data')

np.save('../proc_data/' + date + '_trans.npy', 
	transformation_matrix)
np.save('../proc_data/' + date + '_HPIFitData.npy',
	HPIFitData)
# end of step 5





###################################################################################################################
###################################################################################################################


##############
# Fit one current dipole for each ECD source 
ECDFitData = []
for s in np.arange(numECDs):

	fitData = {}

	# Fit dipole for one source
	pos, dip_opm = dipoleFitEvoked(supportDir, combinedEvokeds_hfc[s])
	
	# Calculate error - Cartesian
	fitData['knownPosition_rpt'] = ecdLocs_rpt[s]
	fitData['knownPosition_xyz'] = ecdLocs_xyz[s]
	fitData['deltaR'] = pos - fitData['knownPosition_xyz']

	# Calculate error - Polar
	fitData['rpt'] = xyz2rpt(pos)
	delta_rpt = fitData['rpt'] - fitData['knownPosition_rpt']

	# Calculate localization error
	fitData['LEmag'] = np.sqrt(np.sum(fitData['deltaR']*fitData['deltaR']))

	fitData['pos'] = pos
	# ECD position translated to coordinate frame of HPIs
	# fitData['pos_prime'] = np.dot(rotMat,(pos-HPIorigin))

	fitData['dip'] = dip_opm

	ECDFitData.append(fitData)

# New pos_prime using ICP (copied from step 7):

# Make an array with all four ECD positions
posData = np.asarray([a['pos'] for a in ECDFitData])
# Transform ECD positions to phantom coordinate frame
pos_prime = apply_transformation(posData, transformation_matrix)
# Add positions in phantom coordinate frame to dictionary
for i in np.arange(4):
	ECDFitData[i]['pos_prime'] = pos_prime[i,:]

######################
# Plot all localized points to one graph
if plotOK:
	colSet = ['b','c','r', 'g']
	mrkSet = ['*', '+', 'o', '^']
	fig = plt.figure()
	ax = fig.add_subplot(projection='3d')
	for ds in np.arange(numECDs):
		a = ECDFitData[ds]['pos']
		ax.scatter(a[0], a[1], a[2], c=colSet[ds])
	for ds in np.arange(numHPIs):
		a = HPIFitData[ds]['pos']
		ax.scatter(a[0], a[1], a[2], c='k', marker=mrkSet[ds])
	ax.set_xlim((-7,7))
	ax.set_ylim((-7,7))
	ax.set_zlim((-1,7))
	ax.set_xlabel('x [cm]')
	ax.set_ylabel('y [cm]')
	ax.set_zlabel('z [cm]')
	plt.show()


#######################################
# Plot raw data from one scan (time and amplitude spectrum)
if plotOK:
	plot_raw_data(raw_filt, raw_detrend, raw_regressed, raw_hfcApplied)

#######################################
# Plot amplitude spectra and shielding factor

if plotOK:
	fig, axs = plt.subplots(1, 3, sharex=True)
	axs_flat = np.ndarray.flatten(axs)

	axs_flat[0].loglog(freq, ampSpecData[0,:,:].T, linewidth=1)
	axs_flat[0].loglog(freq, ampSpec_mean[0,:], 'k', linewidth=3)
	axs_flat[0].set_ylabel('Field Strength [fT/root(Hz)]')
	axs_flat[0].set_ylim((1,1e4))
	axs_flat[0].set_title('Filter + Detrend')

	axs_flat[1].loglog(freq, ampSpecData[1,:,:].T, linewidth=1)
	axs_flat[1].loglog(freq, ampSpec_mean[1,:], 'k', linewidth=3)
	axs_flat[1].set_ylim((1,1e4))
	axs_flat[1].set_title('Cleaned')

	axs_flat[2].plot(freq, shieldFactorSpectrum.T, linewidth=1)
	axs_flat[2].plot(freq, shieldFactor_mean, 'k', linewidth=3)
	axs_flat[2].set_ylabel('Shielding Factor [dB]]')
	axs_flat[2].set_title('Total Shielding')

	for i in np.arange(3):
		axs_flat[i].grid(True, which='both')
		axs_flat[i].set_xlabel('Frequency [Hz]')
		axs_flat[i].set_xscale('linear')
		axs_flat[i].set_xlim((0,30))

	plt.show()

#######################################
# Evoked fields for sensor array   

if plotOK:
	fig, axs = plt.subplots(2,4)
	yscale = 1000
	colscale = (-700,700)
	for i in np.arange(4):
		combinedEvokeds_hfc[i].plot(show=False, axes=axs[0][i], ylim= dict(mag=[-yscale, yscale]), spatial_colors=False, proj=True)
		combinedEvokeds_hfc[i].plot_topomap(show=False, axes=axs[1][i], times=[0], colorbar=False, vlim=colscale, proj=True)
	fig.show()


####################### Editted to give all topos and evokeds
if plotOK:
	fig, axs = plt.subplots(2,4)
	yscale = 1000
	colscale = (-3500,3500)
	for i in np.arange(4):
		combinedEvokeds_hfc[i].plot()
		combinedEvokeds_hfc[i].plot_topomap(times=[0], vlim=colscale)
	fig.show()


print('**** ECDs ******')
print('Qs:')
Qs = [ECDFitData[i]['dip'][5].amplitude for i in np.arange(4)]
print(Qs)
GOFs = [ECDFitData[i]['dip'][5].gof for i in np.arange(4)]
print('Goodness of fits:')
print(GOFs)
POSs = [ECDFitData[i]['pos'] for i in np.arange(4)]
print('positions')
print(POSs)
print()


print('**** HPIs ****')
GOFs = [HPIFitData[i]['gof'] for i in np.arange(4)]
print('Goodness of fits:')
print(GOFs)
POSs = [HPIFitData[i]['pos'] for i in np.arange(4)]
print('positions')
print(POSs)


# Make dataframe 

df_row = -1      #initialize df row

df = pd.DataFrame(columns=['Dataset', 'Source', 'amplitude_x','amplitude_y', 'amplitude_z', 'gof', 
			'rho_known', 'phi_known', 'theta_known', 
			'x_known', 'y_known', 'z_known', 
			'rho_pred','phi_pred', 'theta_pred', 
			'x_pred', 'y_pred', 'z_pred', 
			'rho_prime', 'phi_prime', 'theta_prime',
			'x_prime', 'y_prime', 'z_prime', 'delta_x', 'delta_y', 'delta_z', 'delta_rho', 'delta_phi', 'delta_theta', 'LE', 'delta_x_prime', 'delta_y_prime', 'delta_z_prime',
			'delta_rho_prime', 'delta_phi_prime', 'delta_theta_prime', 'LE_prime' 
								])

for i in np.arange(4):
	df_row +=1

	df.loc[df_row, ['Dataset']] = date
	df.loc[df_row, ['Source']] = f'HPI{i+1}'

	df.loc[df_row, ['gof']] = HPIFitData[i]['gof']
	df.loc[df_row, ['amplitude_x','amplitude_y', 'amplitude_z']] = HPIFitData[i]['amplitude']		

	df.loc[df_row, ['x_known', 'y_known', 'z_known']] = HPIFitData[i]['knownPosition_xyz']
	df.loc[df_row, ['rho_known', 'phi_known', 'theta_known']] = HPIFitData[i]['knownPosition_rpt']

	df.loc[df_row, ['x_pred', 'y_pred', 'z_pred']] = HPIFitData[i]['pos']			# cm
	df.loc[df_row, ['rho_pred', 'phi_pred', 'theta_pred']] = HPIFitData[i]['rpt']

	df.loc[df_row, ['x_prime', 'y_prime', 'z_prime']] = HPIFitData[i]['pos_prime']			# cm
	df.loc[df_row, ['rho_prime', 'phi_prime', 'theta_prime']] = xyz2rpt(df.loc[df_row, ['x_prime', 'y_prime', 'z_prime']])

for i in np.arange(4):
	df_row +=1

	df.loc[df_row, ['Dataset']] = date
	df.loc[df_row, ['Source']] = f'ECD{i+1}'

	df.loc[df_row, ['gof']] = ECDFitData[i]['dip'][5].gof
	df.loc[df_row, ['amplitude_x']] = ECDFitData[i]['dip'][5].amplitude		

	df.loc[df_row, ['x_known', 'y_known', 'z_known']] = ECDFitData[i]['knownPosition_xyz']
	df.loc[df_row, ['rho_known', 'phi_known', 'theta_known']] = ECDFitData[i]['knownPosition_rpt']

	df.loc[df_row, ['x_pred', 'y_pred', 'z_pred']] = ECDFitData[i]['pos']			# cm
	df.loc[df_row, ['rho_pred', 'phi_pred', 'theta_pred']] = ECDFitData[i]['rpt']

	df.loc[df_row, ['x_prime', 'y_prime', 'z_prime']] = ECDFitData[i]['pos_prime']			# cm
	df.loc[df_row, ['rho_prime', 'phi_prime', 'theta_prime']] = xyz2rpt(df.loc[df_row, ['x_prime', 'y_prime', 'z_prime']])

# Add delta columns to the dataframe
df['delta_x_prime'] = pd.to_numeric(df['x_prime'] - df['x_known'], errors='coerce')
df['delta_y_prime'] = pd.to_numeric(df['y_prime'] - df['y_known'], errors='coerce')
df['delta_z_prime'] = pd.to_numeric(df['z_prime'] - df['z_known'], errors='coerce')
df['delta_rho_prime'] = pd.to_numeric(df['rho_prime'] - df['rho_known'], errors='coerce')
df['delta_phi_prime'] = pd.to_numeric(df['phi_prime'] - df['phi_known'], errors='coerce')
df['delta_theta_prime'] = pd.to_numeric(df['theta_prime'] - df['theta_known'], errors='coerce')

df['delta_x'] = pd.to_numeric(df['x_pred'] - df['x_known'], errors='coerce')
df['delta_y'] = pd.to_numeric(df['y_pred'] - df['y_known'], errors='coerce')
df['delta_z'] = pd.to_numeric(df['z_pred'] - df['z_known'], errors='coerce')
df['delta_rho'] = pd.to_numeric(df['rho_pred'] - df['rho_known'], errors='coerce')
df['delta_phi'] = pd.to_numeric(df['phi_pred'] - df['phi_known'], errors='coerce')
df['delta_theta'] = pd.to_numeric(df['theta_pred'] - df['theta_known'], errors='coerce')

df['LE_prime'] = np.sqrt(df['delta_x_prime']**2 +df['delta_y_prime']**2 + df['delta_z_prime']**2)
df['LE'] = np.sqrt(df['delta_x']**2 +df['delta_y']**2 + df['delta_z']**2)


# Correct deltas to range from [-180, 180] for plotting and analysis purposes
for index, val in df['delta_phi_prime'].items():
	if df.loc[index, 'Source'][0:3] == 'ECD':
		if val < -180:
			df.loc[index, 'delta_phi_prime'] = val + 360
		elif val > 180:
			df.loc[index, 'delta_phi_prime'] = val - 360

for index, val in df['delta_phi'].items():
	if df.loc[index, 'Source'][0:3] == 'ECD':
		if val < -180:
			df.loc[index, 'delta_phi'] = val + 360
		elif val > 180:
			df.loc[index, 'delta_phi'] = val - 360
	
### switch location of HPIs for 20250506 so that they are in the same place as for previous scans
if date == '20250506':
	df.iloc[[0, 1]] = df.iloc[[1, 0]].values
	df.iloc[[2, 3]] = df.iloc[[3, 2]].values

df.loc[0, 'Source'] = 'HPI1'
df.loc[1, 'Source'] = 'HPI2'
df.loc[2, 'Source'] = 'HPI3'
df.loc[3, 'Source'] = 'HPI4'

excel_outDir = '../results/all_sources_'+ date + '.xlsx'
df.to_excel(excel_outDir, index=False)