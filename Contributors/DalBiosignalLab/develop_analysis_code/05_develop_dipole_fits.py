from supportFiles.phantom_functions import *

import mne
import numpy as np
import os

def distance_matrix(points):
    """
    points: (N, 3) array of Cartesian coordinates

    returns: (N, N) matrix where D[i, j] is the
             Euclidean distance between points i and j
    """
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    return np.sqrt(np.sum(diff**2, axis=2))

date = '20261007'
numSources = 16
ECDindices = [0,1,2,3,4,5,6,7,10,13,14,15]
HPIindices = [7,8,9,11,12]

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

combinedEvokeds = []
for i in range(numSources):
	evFif = os.path.join(outputDir, fifPre + '_source' + str(i) + '_ev.fif')
	print('Reading: ' + evFif)
	evoked = mne.read_evokeds(evFif)[0]
	combinedEvokeds.append(evoked)

# Fit one magnetic dipole for each HPI source 
HPIFitData = []
ctr = 0
for s in HPIindices:

	# Fit magnetic dipole (in device coordinate frame)
	good_data = mne.pick_types(combinedEvokeds[s].info, meg=True, exclude='bads')
	B_hpi = combinedEvokeds[s].data[good_data,0].T
	x, gof, moment = magDipoleFit(B_hpi, combinedEvokeds[s].info)

	fitData = {}
	fitData['pos'] = x*100			# cm
	fitData['gof'] = gof*100		# %
	fitData['amplitude'] = moment

	#fitData['knownPosition_xyz'] = hpiLocs[ctr]
	#fitData['knownPosition_rpt'] = xyz2rpt(hpiLocs[ctr])
	#fitData['deltaR'] = fitData['pos'] - fitData['knownPosition_xyz']
	#fitData['LEmag'] = np.sqrt(np.sum(fitData['deltaR']*fitData['deltaR']))
	fitData['rpt'] = xyz2rpt(fitData['pos'])

	HPIFitData.append(fitData)

	ctr = ctr + 1


ECDFitData = []
for s in ECDindices:

	fitData = {}

	# Fit dipole for one source
	dip_opm = dipoleFitEvoked(supportDir, combinedEvokeds[s])
	
	ECDFitData.append(dip_opm.pos[0,:]*100)	# cm
ECDFitData = np.asarray(ECDFitData)

fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(projection='3d')
for i in range(len(HPIindices)):
	x,y,z = HPIFitData[i]['pos']
	scatter = ax.scatter(x,y,z) #, c=colors, cmap='viridis', s=40, edgecolors='w')
scatter = ax.scatter(ECDFitData[:,0], ECDFitData[:,1], ECDFitData[:,2], marker='*')
ax.set_xlim(-8,8)
ax.set_ylim(-8,8)
ax.set_zlim(-8,8)
plt.show()


