import mne
import numpy as np
import os
import matplotlib.pyplot as plt

runs = ['A', 'B', 'C', 'D', 'E', 'F', 'G'] #, 'H']
date = '20261007'
numSources = 16

# File prefix
fifPre = 'phantom'
dataDir = '../processed_data'

# Make plots?
plotOK = True
# Write data?
writeOK = True

# Other (fixed) variables
outputDir = os.path.join('../processed_data', date)
supportDir = './supportFiles'

# For each source
allEvokeds = []
for i in np.arange(numSources):
	print("Source # " + str(i))
	# Read in the signed FFT
	numpyFile = os.path.join(outputDir, fifPre + '_source' + str(i) + '_signedFFT.npy')
	FFTdata = np.load(numpyFile) # [channels x 1]
	
	# For each sensor subset
	subEvokeds = []
	for j in np.arange(len(runs)):
		# Read the raw data
		thisRun = runs[j]
		rawFif = fifPre + str(thisRun) + '_cleaned_raw.fif'
		rawFile = os.path.join(outputDir, rawFif)
		raw = mne.io.read_raw_fif(rawFile, preload=True)
		raw.drop_channels(raw.info['bads'])

		# Grab the info
		rawInfo = raw.info
		
		# Get the subset of FFT data relevant for this sensor set 
		firstChannelIndex = j*13
		lastChannelIndex = (j+1)*13
		FFTsubset = FFTdata[firstChannelIndex:lastChannelIndex]

		# Make an evoked variable with the info and signed FFT data
		ev = mne.EvokedArray(np.tile(FFTsubset, (2,1)).T, rawInfo)
		#ev.del_proj(idx='all')

		subEvokeds.append(ev)

	# Combine all channels into one list of evoked variable (one evoked per source_)
	combinedEvokeds = subEvokeds[0].copy()
	for evs in subEvokeds[1::]:
	    combinedEvokeds.add_channels([evs])

	if writeOK:
		outFif = os.path.join(outputDir, fifPre + '_source' + str(i) + '_ev.fif')
		print('Writing: ' + outFif)
		combinedEvokeds.save(outFif, overwrite=True)

	allEvokeds.append(combinedEvokeds)

if plotOK:
	fig, axes = plt.subplots(4, 4, figsize=(15, 15))
	axes_flat = axes.flatten()
	time_to_plot = 0.0 
	for idx, evoked in enumerate(allEvokeds):
	    ax = axes_flat[idx]
	    # Plot the topomap on the designated axis
	    # colorbar=False prevents 16 individual colorbars from crowding the grid
	    evoked.plot_topomap(
	        times=time_to_plot, 
	        axes=ax, 
	        colorbar=False, 
	        show=False,
	        proj=False
	    )
	    # Add a custom title to identify each subplot
	    ax.set_title(f"Evoked {idx}", fontsize=10)
	plt.tight_layout()
	plt.show()
