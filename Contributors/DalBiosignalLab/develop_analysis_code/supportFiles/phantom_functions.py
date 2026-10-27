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
	dip_opm, _ = mne.fit_dipole(combinedEvoked.copy().crop(0,0.001), cov, bemSphere, trans2, verbose=False)

	return dip_opm

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
	class Circle:
	    def __init__(self, radius):
	        self.radius = radius
	a = Circle(5)
	a.radius = R
	#guesses = mne.chpi._make_guesses(
	#    dict(radius=R, r0=np.zeros(3)), grid=0.01, exclude=0.0, mindist=0.005, verbose=safe_false
	#)[0]["rr"]
	guesses = mne.chpi._make_guesses(
	    surf=mne.make_sphere_model(r0=np.zeros(3), head_radius=R), grid=0.01, exclude=0.0, mindist=0.005, verbose=safe_false
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

def ampSpec(raw, n_fft):
	# Amplitude spectra 
	PSDs = raw.compute_psd(n_fft=n_fft, exclude='bads')
	ampSpecData = np.sqrt( PSDs.get_data() ) * 1e15 # in fT
	freq = PSDs.freqs

	return ampSpecData, freq

