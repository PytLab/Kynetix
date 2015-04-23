#Define default shomate parameters
shomate_params = {}
shomate_params['H2_g:298-1000'] = [33.066178,-11.363417,11.432816,
        -2.772874,-0.158558,-9.980797,172.707974,0] #NIST
shomate_params['H2_g:1000-2500'] = [18.563083,12.257357,-2.859786,
        0.268238,1.977990,-1.147438,156.288133,0] #NIST
shomate_params['H2_g:2500-6000'] = [43.413560,-4.293079,1.272428,
        -0.096876,-20.533862,-38.515158,162.081354,0] #NIST
shomate_params['CH4_g:298-1300'] = [-0.703029,108.4773,-42.52157,
        5.862788,0.678565,-76.84376,158.7163,-74.87310] #NIST
shomate_params['CH4_g:1300-1600'] = [85.81217,11.26467,-2.114146,
        0.138190,-26.42221,-153.5327,224.4143,-74.87310] #NIST
shomate_params['CO_g:298-1300'] = [25.56759,6.096130,4.054656,
        -2.671201,0.131021,-118.0089,227.3665,-110.5271] #NIST
shomate_params['CO_g:1300-1600'] = [35.15070,1.300095,-0.205921,
        0.013550,-3.282780,-127.8375,231.7120,-110.5271] #NIST
shomate_params['H2O_g:100-500'] = [36.303952, -24.11232, 63.64111, 
        -38.9524, -0.01385, -10.23966, 237.39431, 0.0] #Fitted to JANAF
shomate_params['H2O_g:500-1700'] = [30.09200,6.832514,6.793435,-2.534480,
        0.082139,-250.8810,223.3967,-241.8264] #NIST
shomate_params['H2O_g:1700-6000'] = [41.96426,8.622053,-1.499780,0.098119,
        -11.15764,-272.1797,219.7809,-241.8264] #NIST
shomate_params['CO2_g:298-1200'] = [24.99735,55.18696,-33.69137,7.948387,
        -0.136638,-403.6075,228.2431,-393.5224] #NIST 
shomate_params['CO2_g:1200-6000'] = [58.16639,2.720075,-0.492289,0.038844,
        -6.447293,-425.9186,263.6125,-393.5224] #NIST
shomate_params['O2_g:100-700'] = [31.32234,-20.23531,57.8664,-36.50624,
        -0.007374,-8.903471,246.7945,0.0] #NIST
shomate_params['O2_g:700-2000'] = [30.03235,8.772972,-3.988133,0.788313,
        -0.741599,-11.32468,236.1663,0.0] #NIST
shomate_params['O2_g:2000-6000'] = [20.91111,10.72071,-2.020498,0.146449,
        9.245722,5.337651,237.6185,0.0] #NIST
shomate_params['NH3_g:298-1400'] = [19.99563,49.77119,-15.37599,1.921168,
        0.189174,-53.30667,203.8591,-45.89806] #NIST
shomate_params['N2_g:100-500'] = [28.98641,1.853978,-9.647459,16.63537,
        0.000117,-8.671914,226.4168,0.0] #NIST
shomate_params['N2_g:500-2000'] = [19.50583,19.88705,-8.598535,1.369784,
        0.527601,-4.935202,212.3900,0.0] #NIST
shomate_params['N2O_g:298-1400'] = [27.67988,51.14898,-30.64454,6.847911,
        -0.157906,71.24934,238.6164,82.04824] #NIST
shomate_params['NO2_g:298-1200'] = [16.10857,75.89525,-54.38740,14.30777,
        0.239423,26.17464,240.5386,33.09502] #NIST
shomate_params['NO_g:298-1200'] = [23.83491,12.58878,-1.139011,-1.497459,
        0.214194,83.35783,237.1219,90.29114] #NIST
shomate_params['NO3_g:298-1200'] = [11.22316,166.3889,-148.4458,47.40598,
            -0.176791,61.00858,221.7679,71.12800] #NIST
shomate_params['HNO2_g:298-1200'] = [24.89974,91.37563,-64.84614,17.92007,
            -0.134737,-88.13596,254.2671,-76.73498] #NIST
shomate_params['HNO3_g:298-1200'] = [19.63229,153.9599,-115.8378,32.87955,
        -0.249114,-146.8818,247.7049,-134.3060] #NIST
shomate_params['HCN_g:298-1200'] = [32.69373,22.59205,-4.369142,-0.407697,
        -0.282399,123.4811,233.2597,135.1432] #NIST
shomate_params['CH2CH2_g:298-1200'] = [-6.387880,184.4019,-112.9718,
        28.49593,0.315540,48.17332,163.1568,52.46694] #NIST
shomate_params['CH2O_g:298-1500'] = [5.193767,93.23249,-44.85457,7.882279,
        0.551175,-119.3591,202.4663,-115.8972] #NIST
shomate_params['CH3OH_g:298-1500'] = [-0.54480506209266066, 
        151.88669435629552, -78.31823594271188, 16.106518370880025, 
        0.49380897934744739, -5.008, 200.05003685507603, 0] 
#Fitted to values from CRC Handbook of Chemistry and Physics 91st Ed.
#H constrained to 0
shomate_params['HCOOH_g:298-1500'] = [3.8027523042252258, 
        153.66217894746168, -84.640467738169264, 16.297377707561505, 
        0.27720649972633382, -6.16527, 212.9698972559699, 0] 
#Fitted to values from Chao et. al. as referenced in NIST.
#H constrained to 0
shomate_params['CH3CH2OH_g:273-1300'] = [6.372731,136.5066*2.,-54.3367*3,
        9.6942975*4,0.334329,-7.25,201,0] 
#Taken from http://www.vscht.cz/fch/cz/pomucky/fchab/D.html


#Define default fixed entropy gas entropies
fixed_entropy_dict = {'H2_g':0.00135,
        'other':0.002
        } 