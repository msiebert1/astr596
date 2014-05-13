"""
Spectra composite program
Authors: Sam, Yixian, Aaron
"""

import matplotlib.pyplot as plt
import numpy as np
import glob
import sqlite3 as sq3
from scipy import interpolate as intp
import math
from astropy.table import Table
import msgpack as msg
import msgpack_numpy as mn
from scipy.optimize import leastsq
from scipy.special import erf
import file_name
import bootstrap
import time

np.set_printoptions(threshold=np.nan)
mn.patch()

#Sets up some lists for later
SN_Array = []
full_array = []
compare_spectrum = []

class supernova(object):
    """Attributes can be added"""

#Connect to database
#Make sure your file is in this location
con = sq3.connect('../data/SNe.db')
cur = con.cursor()

#Pulls in all columns from the database for the selected query
def grab(sql_input):
    print "Collecting data..."
    SN_Array = []
    cur.execute(sql_input)
    for row in cur:
        SN           = supernova()
        SN.filename  = row[0]
        SN.name      = row[1]
	print SN.name
        SN.source    = row[2]
        SN.redshift  = row[3]
        SN.phase     = row[4]
	print SN.phase
        SN.minwave   = row[5]
        SN.maxwave   = row[6]
        SN.dm15      = row[7]
        SN.m_b       = row[8]
        SN.B_minus_v = row[9]
        SN.velocity  = row[10]
        SN.morph     = row[11]
        SN.carbon    = row[12]
        SN.GasRich   = row[13]
        SN.SNR       = row[14]
        interp       = msg.unpackb(row[15])
        SN.interp    = interp
        try:
            SN.wavelength = SN.interp[0,:]
            SN.flux       = SN.interp[1,:]
            SN.ivar       = SN.interp[2,:]
        except TypeError:
            continue
        full_array.append(SN)
        SN_Array.append(SN)
	for i in range(len(SN_Array)-1):
	    if SN_Array[i].name == SN_Array[i-1].name:
		if abs(SN_Array[i].phase) < abs(SN_Array[i-1].phase):
		    del SN_Array[i-1]
    print len(SN_Array), "spectra found"

    #Within the interpolated spectra there are a lot of 'NaN' values
    #Now they become zeros so things work right
    for SN in SN_Array:
        SN.phase_array = np.array(SN.flux)
        SN.dm15_array  = np.array(SN.flux)
        SN.red_array   = np.array(SN.flux)
        SN.vel         = np.array(SN.flux)
        for i in range(len(SN.flux)):
            #Check for NaN
            if np.isnan(SN.flux[i]):
                SN.flux[i]         = 0
                SN.ivar[i]         = 0
                SN.phase_array[i]  = 0
                SN.dm15_array[i]   = 0
                SN.red_array[i]    = 0
                SN.vel[i]          = 0
            
            #Set nonzero values to correct ones
            if SN.phase_array[i] != 0:
                if SN.phase != None:
                    SN.phase_array[i] = SN.phase
                else:
                    SN.phase_array[i] = 0
            if SN.dm15_array[i] != 0:
                if SN.dm15 != None:
                    SN.dm15_array[i] = SN.dm15
                else:
                    SN.dm15_array[i] = 0
            if SN.red_array[i] != 0:
                if SN.redshift != None:
                    SN.red_array[i] = SN.redshift
                else:
                    SN.red_array[i] = 0
            if SN.vel[i] != 0:
                if SN.velocity != None:
                    SN.vel[i] = SN.velocity
                else:
                    SN.vel[i] = 0
                    
    print "Arrays cleaned"
    return SN_Array


#gets as close as possible to matching the compare spectrum wavelength values
def find_nearest(array,value):
    idx = (np.abs(array-value)).argmin()
    return array[idx]

#This is the model for how scales should be applied, used in the find_scales function
def scale_func(vars, in_data, out_data):

    scale  = vars[0]
    model  = scale * in_data
    output = model
    return output[:,0]

#...Finds scales
def find_scales(SN_Array, temp_flux, temp_ivar):
    min_overlap = 300
    scales = []
    print "Finding scales..."
    #loop over each SN in the array
    for SN in SN_Array:
        #grab out the flux and inverse variance for that SN
        flux = SN.flux
        ivar = SN.ivar
        overlap   = temp_ivar * ivar
        n_overlap = len([x for x in overlap if x > 0])

        if n_overlap < min_overlap:

            #If there is insufficient overlap, the scale is zero.
            scales = np.append(scales, np.array([0]), axis = 0)

        else:
            #Otherwise, fit things
            vars = [1.0]
            #Find the appropriate values for scaling
            good      = np.where(overlap > 0)
            flux2     = np.array([flux[good]])
            ivar2     = np.array([ivar[good]])
            tempflux2 = np.array([temp_flux[good]])
            tempivar2 = np.array([temp_ivar[good]])
            totivar   = 1/(1/ivar2 + 1/tempivar2)

            result = np.median(tempflux2/flux2)

            if result < 0:
                result = 0

            #print "Scale factor = ", result

            scales = np.append(scales, np.array([float(result)]), axis = 0)

    return scales

#Scales the data using the factors found before
#If a scale of zero is found, the spectrum's variance becomes zero so it just doesn't count.
badfiles = []
def scale_data(SN_Array, scales):
    print "Scaling..."
    for i in range(len(scales)):
        if scales[i] != 0:
            SN_Array[i].flux *= np.abs(scales[i])
            SN_Array[i].ivar /= (scales[i])**2
            #print "Scaled at factor ", scales[i]
        else:
            SN_Array[i].ivar = np.zeros(len(SN_Array[i].ivar))
    return SN_Array

#averages with weights of the inverse variances in the spectra
def average(SN_Array, template, medmean):
        print "Averaging..."
        #print fluxes, errors
        fluxes = []
        ivars  = []
        reds   = []
        phases = []
        ages   = []
        vels   = []
        dm15s  = []
        for SN in SN_Array:
            if len(fluxes) == 0:
                fluxes = np.array([SN.flux])
                ivars  = np.array([SN.ivar])
                reds   = np.array([SN.red_array])
                phases = np.array([SN.phase])
                ages   = np.array([SN.phase_array])
                vels   = np.array([SN.vel])
                dm15s  = np.array([SN.dm15_array])
            else:
                try:
                    fluxes = np.append(fluxes, np.array([SN.flux]), axis=0)
                    ivars  = np.append(ivars, np.array([SN.ivar]), axis=0)
                    reds   = np.append(reds, np.array([SN.red_array]), axis = 0)
                    phases = np.append(phases, np.array([SN.phase]), axis = 0)
                    ages   = np.append(ages, np.array([SN.phase_array]), axis = 0)
                    vels   = np.append(vels, np.array([SN.vel]), axis = 0)
                    dm15s  = np.append(dm15s, np.array([SN.dm15_array]), axis = 0)
                except ValueError:
                    print "This should never happen!"

        #Adding masks for every parameter for consistency and zero compensation
        flux_mask = np.zeros(len(fluxes[0,:]))
        ivar_mask = np.zeros(len(fluxes[0,:]))
        dm15_mask = np.zeros(len(dm15s[0,:]))
        red_mask  = np.zeros(len(reds[0,:]))
        
        have_data = np.where(np.sum(ivars, axis = 0)>0)
        no_data   = np.where(np.sum(ivars, axis = 0)==0)
        no_dm15   = np.where(np.sum(dm15s, axis = 0)==0)
        no_reds   = np.where(np.sum(reds, axis = 0)==0)
        
        ivar_mask[no_data] = 1
        dm15_mask[no_dm15] = 1
        
        #Right now all of our spectra have redshift data, so a mask is unnecessary
        #One day that might change?
        red_mask[:]  = 1
        
        dm15_ivars = np.array(ivars)
        red_ivars  = np.array(ivars)
        
        
        #Add in flux/ivar mask
        fluxes = np.append(fluxes, np.array([flux_mask]), axis=0)
        ivars  = np.append(ivars, np.array([ivar_mask]), axis=0)
        reds   = np.append(reds, np.array([flux_mask]), axis=0)
        ages   = np.append(ages, np.array([flux_mask]), axis=0)
        vels   = np.append(vels, np.array([flux_mask]), axis=0)
        dm15s  = np.append(dm15s, np.array([dm15_mask]), axis=0)
        dm15_ivars = np.append(dm15_ivars, np.array([dm15_mask]), axis=0)
        red_ivars  = np.append(red_ivars, np.array([red_mask]), axis=0)

        for i in range(len(dm15s)):
            if np.all(dm15s[i]) == 0:
                np.delete(dm15s, i)
                np.delete(dm15_ivars, i)

        if medmean == 1:
            template.flux  = np.average(fluxes, weights=ivars, axis=0)
            template.phase_array   = np.average(ages, weights=ivars, axis=0)
            template.vel   = np.average(vels, weights=ivars, axis=0)
            template.dm15  = np.average(dm15s, weights=dm15_ivars, axis=0)
            template.red_array = np.average(np.array(reds), weights = red_ivars, axis=0)
        if medmean == 2:
            template.flux  = np.median(fluxes, axis=0)
            template.phase_array   = np.median(ages, axis=0)
            template.vel   = np.median(vels, axis=0)
            template.dm15  = np.median(dm15s, axis=0)
            template.red_array = np.median(reds, axis=0)
        template.ivar = 1/np.sum(ivars, axis=0)
        template.ivar[no_data] = 0
        template.name = "Composite Spectrum"
        return template



def main(Full_query, showplot = 0, medmean = 1, opt = 'n', save_file = 'y'):
    SN_Array = []

    #Accept SQL query as input and then grab what we need
    print "SQL Query:", Full_query
    SN_Array = grab(Full_query)
    
    if opt == 'y':
        bootstrap.main(SN_Array)

    if opt == 'n':
        #finds the longest SN we have for our initial template
        lengths = []
        for SN in SN_Array:
            lengths.append(len(SN.flux[np.where(SN.flux != 0)]))
        temp = [SN for SN in SN_Array if len(SN.flux[np.where(SN.flux!=0)]) == max(lengths)]
        try:
            composite = temp[0]
        except IndexError:
            print "No spectra found"
            exit()



        #Here is where we set our wavelength range for the final plot
        wmin    = 4000
        wmax    = 7500
        wavemin = composite.minwave
        wavemax = composite.maxwave

        #finds range of useable data
        good     = np.where(len(np.where(((wavemin <= wmin) & (wavemax >= wmax)) > 100)))
        template = supernova()
        template = SN_Array[good[0]]
        template = composite

        #Starts our main loop
        #scales data, makes a composite, and splices in non-overlapping data
        i = 0
        n_start = 0
        n_end   = 1
        scales  = []
        while (n_start != n_end):
            n_start = len([x for x in scales if x>0])
            scales   = []
            scales   = find_scales(SN_Array, template.flux, template.ivar)
            n_scale  = len([x for x in scales if x>0])
            SN_Array = scale_data(SN_Array, scales)
            template = average(SN_Array, template, medmean)
            n_end    = n_scale
            n_start  = n_end


        print "Done."

        #This next line creates a unique filename for each run based on the sample set used
        #### file_name.py needs to be adjusted
        #f_name = "../plots/" + file_name.make_name(SN_Array)
        f_name = "../plots/" + "Test_composite" + (time.strftime("%H,%M,%S"))
        template.savedname = f_name + '.dat'
        lowindex  = np.where(template.wavelength == find_nearest(template.wavelength, wmin))
        highindex = np.where(template.wavelength == find_nearest(template.wavelength, wmax))

        #This plots the individual composite just so you can see how it looks
        #Also it gets saved. Comment that line out if you don't want it to.
        if int(showplot) == 1:
            plt.plot(template.wavelength[lowindex[0]:highindex[0]], template.flux[lowindex[0]:highindex[0]])
            plt.plot(template.wavelength[lowindex[0]:highindex[0]], template.ivar[lowindex[0]:highindex[0]])
            plt.savefig('../plots/' + f_name + '.png')
            plt.show()
        table = Table([template.wavelength, template.flux, template.ivar, template.phase_array, template.vel, template.dm15, template.red_array], names = ('Wavelength', 'Flux', 'Variance', 'Age', 'Velocity', 'Dm_15', 'Redshift'))
        return table

if __name__ == "__main__":
    main()
