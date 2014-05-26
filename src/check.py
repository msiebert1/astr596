import glob
import composite
import Plotting
from astropy.table import Table
import matplotlib.pyplot as plt
import numpy as np

import sqlite3 as sq3
from scipy import interpolate as intp
import math
import msgpack as msg
import msgpack_numpy as mn
from prep import *
from datafidelity import *

"""
*Meant to be used from src folder

This code is designed to check each spectra file, one by one, given a particular source,
by plotting the original and the interpolated spectra together, along with the 
inverse varience.  

comments can be given to note telluric absorption, errors in reddening, spikes in fluxes,
clipping, or any other problems with either the original or interpolated spectra
"""

"""
ROUGH OUTLINE OF CODE
-select SOURCE (bsnip,cfa,csp,other,uv)
-pull all FILENAMES from selected source
-select START index [0 to (len(source)-1))]

MAIN LOOP:	
	-read data at index (from START)
	-create separate interpolated data INTERP
	-get inverse varience values INVAR
	-plot ORIG and INTERP data 
	 with INVAR
	-Observe and Comment:
		-[enter](blank input)
		 	plot is fine(don't add to list)
		-type comment(telluric, spikes, etc...)
		 	added to 2 column list-> |FILENAME|COMMENT|
		-'q' or 'quit' to end, saves ending index END
	-Continues onto next file

	When Quitting:
		save list to file in format: 
		('SOURCE_'+'START'+'_'+'END')
		ex. ('cfa_0_200.dat')

===========
guidelines:
===========
[ ] - need to implement
[x] - implemented

#comment on the functionality of the blocks of code
##commented out code that does checks on the functionality of code
==========
variables: (work in progress)
==========
SOURCE		which source data is being looked at(bsnip,cfa,etc.)
FILENAMES	path to the spectra files
FILES		truncated path list to match the data being looked at
DATA		data from the spectra files
BADLIST		holds filename that has problems
BADCOMMENT	holds the comment associated with the bad file

START		index started at
END		index ended at

"""

#Select which data you want to check, will loop until a correct data source is selected
while (True):
	source = str(raw_input("Please select which data to check(type one of the following):\nbsnip\ncfa\ncsp\nother\nuv\n:"))
	if(source != 'bsnip' and source !='cfa' and source !='csp' and source !='other' and source !='uv'):
		print "\ninvalid data selection\n"
	else:
		print "checking",source
		break

#accounts for different file organizations for sources
if source == 'bsnip' or source == 'uv':
	path = "../data/spectra/"+source+"/*.flm"
if source == 'cfa':
	path = "../data/spectra/"+source+"/*/*.flm"
if source == 'csp' or source == 'other':
	path = "../data/spectra/"+source+"/*.dat"


#read in all filenames to extract data from 
filenames = glob.glob(path)

###checks that all the files were correctly read in
##for files in filenames:
##	print files

#select an index value to start at so you don't have to check a set of data
#from the beginning every time you run the program
while (True):
	print "valid index range: 0 to",(len(filenames)-1)
	start = int(raw_input("Please select what index you would like to start at:\n"))
	if (start < 0 and start > (len(filenames)-1)):
		print "\ninvalid index"
	else:
		print "starting at index:",start		
		break

"""
#trims filenames so that cuts out the path and leaves only the file
for i in range(len(filenames)):
	if source == 'cfa':
		filenames[i] = filenames[i].split('/')[5]
	else:
		filenames[i] = filenames[i].split('/')[4]

###checks that all filenames were correctly split
##for files in filenames:
##	print files
"""

data = []
wave = []
flux = []
badlist = []
badcomment = []
interp = []
invar = []
end = -1

"""
[ ] - need to implement
[x] - implemented

MAIN LOOP CHECKLIST:

	For each spectra file:

	[x]read data at index (from START)
	[x]except value error for bad file
	[x]make sure FILE lines up with DATA
	[]create separate interpolated data INTERP
	[]get inverse varience values INVAR
	[]plot ORIG and INTERP data 
	 with INVAR
	[]Observe and Comment(for BADLIST and BADCOMMENT):
		[][enter](blank input)
		 	plot is fine(don't add to list)
		[]type comment(telluric, spikes, clipping, etc...)
		 	add FILES[i] to BADLIST and 
			keyboard input to BADCOMMENT
		[]'q' or 'quit' to end, saves ending index to END
	[x]Continues onto next file if not quitting

	if quitting:
		[]combine BADLIST and BADCOMMENT into 2-column list
		[]save list to txt file in format: 
		('SOURCE_'+'START'+'_'+'END')
		ex. ('cfa_0_200.txt')

"""
files = []


########
#right now generating varience for all...implement check to see if file already has it (too lazy right now)
#######
#main loop, see MAIN LOOP CHECKLIST above for breakdown
offset = start
for i in range(len(filenames)):
	if (i >= start):
		try:
			###checks that correct data files are appended 
			###when taking into account the index offset
			##print i,filenames[i]

			#gets wave and flux from current file
			data.append((np.loadtxt(filenames[i])))
			#keeps track of files looking at (due to index offset)
			files.append(filenames[i])
			#separate wave/flux/error for easier manipulation
			orig_wave = data[i-offset][:,0]
			orig_flux = data[i-offset][:,1]
			try:
				# check if data has error array
				orig_error = data[i-offset][:,2] 
		   	except IndexError:
				# if not, set default
				orig_error = np.array([0])

			##get invar, to use in interp, and separate wave/flux/errors
			invar = genivar(orig_wave,orig_flux)
			interp = Interpo(orig_wave,orig_flux,invar)
			interp_wave = interp[0]
			interp_flux = interp[1]
			interp_error = interp[2]

			##plotting orig, interp, var


			Relative_Flux = [orig_wave, orig_flux, interp_wave, interp_flux]  # Want to plot a composite of multiple spectrum
			Variance = invar
			Residuals     = []
			Spectra_Bin   = []
			Age           = []
			Delta         = []
			Redshift      = [] 
			Show_Data     = [Relative_Flux,Variance,Residuals,Spectra_Bin,Age,Delta,Redshift]
			image_title   = source,i            # Name the image (with location)
			title         = "(>^.^)> <(^.^<) ^(^.^)v v(^.^)^" 
			#
			## Available Plots:  Relative Flux, Residuals, Spectra/Bin, Age, Delta, Redshift, Multiple Spectrum, Stacked Spectrum
			##                   0              1          2            3    4      5         6,                 7
			####################################^should be varience?...
			name_array = ["original", " ", "interpolated", " "]
			Names = name_array
			Plots = [0,1] # the plots you want to create
			#
			## The following line will plot the data
			#
			xmin         = 1500 
			xmax         = 12000
			Plotting.main(Show_Data , Plots , image_title , title, Names,xmin,xmax)
			

		except ValueError:
			print "found bad file! at index:",i
			badlist.append(filenames[i])
			badcomment.append("bad file")
			offset += 1


###checks to make sure the right data is being looked at
##print "looking at",files[0],"with wave vals:\n",data[0][:,0]	#all wavelengths of data at index 0
##print "looking at",files[0],"with flux vals:\n",data[0][:,1]	#all flux values of data at index 0

###double-check to make sure right number of data are appended
##print len(filenames),"- starting index",start,"=",len(data)
##print badlist,badcomment





