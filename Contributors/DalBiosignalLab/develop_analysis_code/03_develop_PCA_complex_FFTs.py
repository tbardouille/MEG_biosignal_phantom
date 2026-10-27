import mne
import numpy as np
from sklearn.decomposition import PCA
import os
import matplotlib.pyplot as plt

runs = ['A', 'B', 'C', 'D', 'E', 'F', 'G'] #, 'H']
date = '20261007'
numSources = 16

# Cleaned?
cleaned = False

# File prefix
fifPre = 'phantom'
dataDir = '../processed_data'

# Make plots?
plotOK = True
# Write data?
writeOK = True

PCAmethod = 3

# Other (fixed) variables
outputDir = os.path.join('../processed_data', date)
supportDir = './supportFiles'

## Across runs, stack all complex FFTs into one matrix [channels x driver signals]
allFFTs = []
for r in np.arange(len(runs)):
	thisRun = runs[r]
	numpyFile = os.path.join(outputDir, fifPre + str(thisRun) + '_complexFFT.npy')
	stimFFTs = np.load(numpyFile)
	allFFTs.append(stimFFTs)
fftArray = allFFTs[0]
numDatasets = len(runs)
for i in np.arange(1,numDatasets):
	fftArray = np.vstack((fftArray,allFFTs[i]))

# Per source, PCA analysis on complex FFT to get signed amplitude at each frequency 
allPCA_FFTs = []
for i in range(numSources):

	if PCAmethod == 1:
		FFT_PCA = np.column_stack((np.imag(fftArray[:, i]), np.real(fftArray[:, i])))
		cov_matrix = np.dot(FFT_PCA.T, FFT_PCA) / (FFT_PCA.shape[0] - 1)
		eigenvalues, rotation_matrix = np.linalg.eigh(cov_matrix)
		idx = np.argsort(eigenvalues)[::-1]
		rotation_matrix = rotation_matrix[:, idx]
		stimFFT_PCA = FFT_PCA @ rotation_matrix

	if PCAmethod == 2:
		# Old code: stretched transform
		stimReal = np.real(fftArray[:,i])
		stimImag = np.imag(fftArray[:,i])
		signalX = stimImag 
		signalY = stimReal
		FFT_PCA = np.column_stack((signalX, signalY))
		pca = PCA(n_components=2)
		pca.fit(FFT_PCA)
		stimFFT_PCA = FFT_PCA @ pca.components_.T   

	if PCAmethod == 3:
		stimReal = np.real(fftArray[:,i])
		stimImag = np.imag(fftArray[:,i])
		x = stimImag 
		y = stimReal
		variances_y = []
		all_x_rot = []  # List to store the 91 x_rot values for each of the 1,801 steps
		all_y_rot = []  # Optional: track y_rot as well if needed
		angles_deg = np.arange(0, 180.1, 0.1)
		angles_rad = np.radians(angles_deg)
		for rad in angles_rad:
		    # Full 2D Rotation Matrix transformations
		    x_rot = x * np.cos(rad) + y * np.sin(rad)
		    y_rot = - x * np.sin(rad) + y * np.cos(rad)
		    # Store calculations
		    all_x_rot.append(x_rot)
		    all_y_rot.append(y_rot)
		    variances_y.append(np.var(y_rot))
		# Convert to arrays for easy indexing
		variances_y = np.array(variances_y)
		all_x_rot = np.array(all_x_rot)  # Shape will be (1801, 91)
		all_y_rot = np.array(all_y_rot)  # Shape will be (1801, 91)
		# Extract x_rot at minimum variance ---
		min_idx = np.argmin(variances_y)
		min_angle = angles_deg[min_idx]
		# This is your final array of 91 values
		x_rot_at_min_y_var = all_x_rot[min_idx] 
		y_rot_at_min_y_var = all_y_rot[min_idx]
		stimFFT_PCA = np.vstack((x_rot_at_min_y_var, y_rot_at_min_y_var)).T

	allPCA_FFTs.append(stimFFT_PCA)

if plotOK:
	# Make a 4x4 plot where each is a scatter plot
	plotLimit = 10e-13
	fig, axes = plt.subplots(
	    nrows=4,
	    ncols=4,
	    figsize=(20, 14),
	    sharex=True,
	    sharey=True,
	)
	axes = axes.ravel()
	for i in range(numSources):
		ax = axes[i]
		ax.scatter(np.real(fftArray[:,i]), np.imag(fftArray[:,i]))
		ax.scatter(allPCA_FFTs[i][:,0], allPCA_FFTs[i][:,1])
		ax.set_xlim(-plotLimit, plotLimit)
		ax.set_ylim(-plotLimit, plotLimit)
		ax.grid(True)
	plt.show()

if writeOK:
	for i in range(numSources):
		numpyFile = os.path.join(outputDir, fifPre + '_source' + str(i) + '_signedFFT.npy')
		print("Writing: " + numpyFile)
		np.save(numpyFile, allPCA_FFTs[i][:,0])
		
