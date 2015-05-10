from pynetics import ModelShell
import mpmath as mp
from scipy.optimize import golden
import numpy as np
from pynetics.functions import numerical_jacobian
from scipy.integrate import odeint
import gmpy2
import sympy as sym


class SolverBase(ModelShell):
    def __init__(self, owner):
        """
        A class acts as a base class to be inherited by other
        solver classes, it is not functional on its own.
        """
        ModelShell.__init__(self, owner)
        #mp.mp.dps = self._owner.decimal_precision

        #set default parameter dict
        defaults = dict(
            perturbation_size=0.01,
            perturbation_direction='right',
            numerical_representation='mpmath',
            archived_variables=['steady_state_coverage', 'rates'],
            )
        defaults = self.update_defaults(defaults)
        self.__dict__.update(defaults)

        #set numerical represention
        if self.numerical_representation == 'mpmath':
            #import mpmath as mp
            mp.mp.dps = self._owner.decimal_precision
            self._math = mp  # to do math operations
            self._linalg = mp
            self._mpf = mp.mpf
            self._matrix = mp.matrix
            self._Axb_solver = mp.lu_solve
            self._norm = lambda x: mp.norm(x, p=2)

        elif self.numerical_representation == 'gmpy':
            #import gmpy2
            gmpy2.get_context().precision = 3*self._owner.decimal_precision
            self._math = gmpy2
            self._linalg = np
            self._mpf = gmpy2.mpfr

            def cus_matrix(*args):
                if len(args) == 1:
                    mat = np.matrix(args[0])
                    mat_shape = mat.shape
                    if mat_shape[0] == 1 and mat_shape[1] > 1:
                        mat.shape = (-1, 1)
                    return mat
                elif len(args) == 2:
                    return np.matrix(np.empty(args, object))

            self._matrix = cus_matrix
            self._Axb_solver = np.linalg.solve
            self._norm = lambda x: \
                gmpy2.sqrt(np.sum(np.square(x)))  # x is a column vector

        elif self.numerical_representation == 'sympy.mpmath':
            import sympy.mpmath as symp
            symp.mp.dps = self._owner.decimal_precision
            self._math = symp
            self._linalg = symp
            self._mpf = symp.mpf
            #self._mpf = lambda x: \
            #    sym.N(sym.RealNumber(str(x), 100), 100)
            self._matrix = symp.matrix
            self._Axb_solver = symp.lu_solve
            self._norm = lambda x: symp.norm(x, p=2)

        elif self.numerical_representation == 'sympy':
            #import sympy as sym
            self._math = sym
            self._linalg = sym
            precision = self._owner.decimal_precision
            self._mpf = lambda x: \
                sym.N(sym.RealNumber(str(x), precision), precision)

            def cus_matrix(*args):
                if len(args) == 1:
                    return sym.Matrix(args[0])
                elif len(args) == 2:
                    return sym.zeros(*args)

            self._matrix = cus_matrix
            self._Axb_solver = lambda A, b: A.LUsolve(b)
            self._norm = lambda x: sym.sqrt((x.transpose()*x)[0])  # x is a column vector

        self.has_data = False
        self.energy_correction = False
        self.has_symbols = False

        #set essential attrs for solver
        setattr(self, 'rxns_list', self._owner.elementary_rxns_list)
        setattr(self, 'rxns_num', len(self.rxns_list))

        #set constants symbol dict
#        import sympy as sym
        self.k_B_sym, self.h_sym, self.T_sym = \
            sym.symbols('k_B, h, T', is_real=True)
        self.constants_subs_dict = {
            self.k_B_sym: self._mpf(self._owner._kB),
            self.h_sym: self._mpf(self._owner._h),
            self.T_sym: self._mpf(self._owner.temperature),
        }

        if self._owner.hasdata:
            self.get_data_dict()
            self.get_rate_constants()

        self.classify_adsorbates()

    def classify_adsorbates(self):
        "Classify coverages according to type of site, return a dict"
        classified_adsorbates = {}
        for site_name in self._owner.site_names:
            classified_adsorbates.setdefault(site_name, [])
        for adsorbate_name in self._owner.adsorbate_names:
            site_name = self._owner.species_definitions[adsorbate_name]['site']
            classified_adsorbates[site_name].append(adsorbate_name)
        setattr(self, 'classified_adsorbates', classified_adsorbates)
        return classified_adsorbates

    def get_data_dict(self):   # !!!correction added base on the values got in here!!!
        """
        Assign gas pressure, formation_energy of sites and
        species, frequencies as attrs of solver.
        """
        if not self._owner.hasdata:
            raise AttributeError('model object has '
                                 'no input data in species_definitions')
        #get gas pressure dict
        p_dict = {}
        for gas_name in self._owner.gas_names:
            p_dict.setdefault(
                gas_name,
                self._mpf(self._owner.species_definitions[gas_name]['pressure'])
            )

        #get energy, frequencies dict
        E_dict, frequencies_dict = {}, {}
        for species in self._owner.species_definitions:
            if self._owner.species_definitions[species]['type'] == 'site':
                key = '*_' + species
            else:
                key = species
            energy = self._mpf(self._owner.species_definitions
                               [species]['formation_energy'])
            frequencies = [self._mpf(frequency) for frequency in
                           self._owner.species_definitions[species]['frequencies']]
            E_dict.setdefault(key, energy)
            frequencies_dict.setdefault(key, frequencies)
        setattr(self, 'energy_correction', False)
        self.p, self.E, self.frequencies = p_dict, E_dict, frequencies_dict
        self.has_data = True

    def get_reaction_energies(self, elementary_rxn_list):
        """
        Analyse a single elementary rxn equation,
        return list of reaction_barrier(delta_G) and
        reaction energy for the elementary rxn.
        """
        #get free energy for states
        G_IS, G_TS, G_FS = 0.0, 0.0, 0.0
        for sp in elementary_rxn_list[0]:
            stoichiometry, species_name = self.split_species(sp)
            G_IS += stoichiometry * self.E[species_name]
        for sp in elementary_rxn_list[-1]:
            stoichiometry, species_name = self.split_species(sp)
            G_FS += stoichiometry * self.E[species_name]

        if len(elementary_rxn_list) == 2:
            G_TS = max(G_IS, G_FS)
        if len(elementary_rxn_list) == 3:
            for sp in elementary_rxn_list[1]:
                stoichiometry, species_name = self.split_species(sp)
                G_TS += stoichiometry * self.E[species_name]

#        return [G_IS, G_TS, G_FS]
        #calculate delta G for one elementary rxn
        f_barrier, r_barrier = G_TS - G_IS, G_TS - G_FS
        #reaction_energy = G_FS - G_IS
        return f_barrier, r_barrier

    def get_single_state_energy_dict(self, elementary_rxn_list):
        """
        Go through elementary_rxn_list,
        return a dict containing energies of states.
        """
        single_state_energy_dict = {}
        for state in elementary_rxn_list:
            state_energy = 0.0
            for sp in state:
                stoichiometry, species_name = self.split_species(sp)
                sp_energy = stoichiometry*self.E[species_name]
                state_energy += sp_energy
            state_str = ' + '.join(state)
            single_state_energy_dict.setdefault(state_str, state_energy)

        return single_state_energy_dict

    def get_state_energy_dict(self):
        state_energy_dict = {}
        for elementary_rxn_list in self._owner.elementary_rxns_list:
            single_state_energy_dict = \
                self.get_single_state_energy_dict(elementary_rxn_list)
            state_energy_dict.update(single_state_energy_dict)
        setattr(self._owner, 'state_energy_dict', state_energy_dict)

        return state_energy_dict

    def get_rate_constants(self):
        "Go through rxns_list to get all delta_G and rate constants"
        delta_Gfs, delta_Grs, kfs, krs = [], [], [], []
        kB, h, T = [self._mpf(constant) for constant in
                    [self._owner._kB, self._owner._h, self._owner.temperature]]
        prefactor = kB*T/h
        for elementary_rxn in self.rxns_list:
            delta_Gf, delta_Gr = self.get_reaction_energies(elementary_rxn)
            delta_Gfs.append(delta_Gf)
            delta_Grs.append(delta_Gr)
            #rate constant
            kf = prefactor*self._math.exp(-delta_Gf/(kB*T))
            kr = prefactor*self._math.exp(-delta_Gr/(kB*T))
            kfs.append(kf)
            krs.append(kr)
        self._Gaf, self._Gar, self._kfs, self._krs = \
            map(tuple, [delta_Gfs, delta_Grs, kfs, krs])
        return tuple(kfs), tuple(krs)

    def boltzmann_coverages(self):
        """
        Return a boltzmann coverages list
        according to adsorbation energy of adsorbates.
        """
        free_site_names = \
            tuple(['*_' + site for site in self._owner.site_names])
        self._cvg_types = self._owner.adsorbate_names + free_site_names
        kB, h, T = [self._mpf(constant) for constant in
                    [self._owner._kB, self._owner._h, self._owner.temperature]]
        #check whether solver has load data from species_definition
        if not self.has_data:
            self.get_data_dict()
#        boltz_sum = sum([mp.exp(-self.E[adsorbate]/(kB*T))
#                         for adsorbate in self._cvg_types])
        boltz_sum = sum([self._math.exp(-self.E[adsorbate]/(kB*T))
                         for adsorbate in self._owner.adsorbate_names])
        #get coverages list
        cvgs = []
        for adsorbate in self._owner.adsorbate_names:
            cvg = self._math.exp(-self.E[adsorbate]/(kB*T))/boltz_sum
            cvgs.append(cvg)
        return tuple(cvgs)

    def get_elementary_rate_expression(self, elementary_rxn_list):
        """
        Expect a elementary_rxn list, e.g.[['3H2_g', '6*_s'], ['6H_s']]
        return a tuple of forward and reverse rxn rate expressions.
        e.g. "kf[0]*p['CO_g']*theta['*_s']"
        """
        idx = self.rxns_list.index(elementary_rxn_list)

        def list2string(sp_list, direction):
            if direction == 'f':
                rate_str = 'kf['+str(idx)+']'
            if direction == 'r':
                rate_str = 'kr['+str(idx)+']'

            for sp in sp_list:
                stoichiometry, species_name = self.split_species(sp)
                #get type of species
                if '*' in sp:
                    if stoichiometry == 1:
                        sp_expr = "*theta['"+species_name+"']"
                    else:
                        sp_expr = "*theta['"+species_name+"']**"+str(stoichiometry)
                else:
                    sp_type = self._owner.species_definitions[species_name]['type']
                    if sp_type == 'adsorbate':
                        if stoichiometry == 1:
                            sp_expr = "*theta['"+species_name+"']"
                        else:
                            sp_expr = "*theta['"+species_name+"']**"+str(stoichiometry)
                    if sp_type == 'gas':
                        if stoichiometry == 1:
                            sp_expr = "*p['"+species_name+"']"
                        else:
                            sp_expr = "*p['"+species_name+"']**"+str(stoichiometry)
                rate_str += sp_expr
            return rate_str
#        f_list, r_list = elementary_rxn_list[0], elementary_rxn_list[-1]
        f_expr, r_expr = list2string(elementary_rxn_list[0], direction='f'),\
            list2string(elementary_rxn_list[-1], direction='r')
        return f_expr, r_expr

    def get_rate_expressions(self, rxns_list):
        """
        Expect elementary_rxns_list,
        return a list of forward rate expressions,
        and a list of reverse rate expressions.
        e.g. "rf[0] = kf[0]*p['CO_g']*theta['*_s']"
        """
        f_rate_expressions, r_rate_expressions = [], []
        for rxn_list in rxns_list:
            f_expr, r_expr = self.get_elementary_rate_expression(rxn_list)
            idx = rxns_list.index(rxn_list)
            f_rate_expressions.append('rfs['+str(idx)+'] = ' + f_expr)
            r_rate_expressions.append('rrs['+str(idx)+'] = ' + r_expr)
        setattr(self, 'rate_expressions',
                (f_rate_expressions, r_rate_expressions))
        return f_rate_expressions, r_rate_expressions

    def get_rates(self, rate_expressions, cvgs_tuple):
        """
        Expect rate_expressions and a coverage tuple,
        return forward and reverse rates list.
        """
        #set theta, kf, kr, p, dtheta_dt
        #coverages(theta)
        theta = self.cvg_tuple2dict(cvgs_tuple)
        #rate constants(kf, kr)
        kf, kr = self.get_rate_constants()
        #pressure
        p = self.p
        #rate list
        rfs, rrs = [0]*len(self._owner.elementary_rxns_list), \
            [0]*len(self._owner.elementary_rxns_list)

        for exprs_list in rate_expressions:
            exprs_str = '\n'.join(exprs_list)
            exec exprs_str in locals()
        rfs, rrs = map(tuple, (rfs, rrs))
        setattr(self, '_rates', (rfs, rrs))
        #archive
        self.logger.archive_data('rates', (rfs, rrs))

        return rfs, rrs

    def get_net_rates(self, rfs, rrs):
        net_rates = tuple([rf - rr for rf, rr in zip(rfs, rrs)])
        setattr(self, 'net_rates', net_rates)
        #archive
        self.logger.archive_data('net_rates', net_rates)
        return net_rates

    def get_reversibilities(self, rfs, rrs):
        "Return a list of reversibilities."
        if len(rfs) != len(rrs):
            raise ValueError('Different rates number is detected.')
        zipped_rates = zip(rfs, rrs)

        reversibilities = [float(rate_tuple[1]/rate_tuple[0])
                           for rate_tuple in zipped_rates]
        setattr(self, 'reversibilities', reversibilities)
        #archive
        self.logger.archive_data('reversibilities', reversibilities)

        return reversibilities

    def get_tof(self, Gs):  # Gs -> free energies
        """
        Expect free energies of intermediates in kinetic model,
        return turnover frequencies.
        """
        #get net rates firstly
        #change the E of solver
        Gs_order = self._owner.adsorbate_names + \
            self._owner.transition_state_names
        setattr(self, 'Gs_order', Gs_order)

        #self.get_data_dict()    #refresh data for solver
        for intermediate, G in zip(Gs_order, Gs):
            self.E[intermediate] = G

        #get net rates about new Gs
        self.get_rate_constants()
        #get initial guess
        init_guess = self.initial_guess
        steady_state_cvg = self.get_steady_state_cvgs(init_guess)
        #check whether solver has rate_expressions
        if not hasattr(self, 'rate_expressions'):  # if not, get it
            self.get_rate_expressions(self.rxns_list)
        rfs, rrs = self.get_rates(self.rate_expressions, steady_state_cvg)
        net_rates = self.get_net_rates(rfs, rrs)

        #get turnover frequencies
        if hasattr(self._owner, 'gas_matrix'):
            gas_matrix = self._owner.gas_matrix
        else:
            gas_matrix = \
                self._owner.parser.get_stoichiometry_matrices()[1]
        #gas_matrix *= -1
        gas_matrix = abs(gas_matrix)
        rate_vector = np.matrix(net_rates)  # get rate vector
        tof_list = (rate_vector*gas_matrix).tolist()[0]
        setattr(self, 'tof', tof_list)
        #archive
        self.logger.archive_data('tofs', tof_list)

        return tof_list

    def get_cvg_tof(self, cvgs):
        """
        Expect a certain coverage of intermediates,
        return turnover frequencies wrt gases.
        """
        #get net rates wrt the coverages c
        self.get_rate_constants()
        rfs, rrs = self.get_rates(self.rate_expressions, cvgs)
        net_rates = self.get_net_rates(rfs, rrs)

        #get turnover frequencies
        if hasattr(self._owner, 'gas_matrix'):
            gas_matrix = self._owner.gas_matrix
        else:
            gas_matrix = \
                self._owner.parser.get_stoichiometry_matrices()[1]
        #gas_matrix *= -1
        gas_matrix = abs(gas_matrix)
        rate_vector = np.matrix(net_rates)  # get rate vector
        tof_list = (rate_vector*gas_matrix).tolist()[0]
        setattr(self, 'tof', tof_list)
        #archive
        self.logger.archive_data('tofs', tof_list)

        return tof_list

    def get_intermediates_Gs(self):
        #get Gs
        Gs = []
        for intermediates_name in \
                self._owner.adsorbate_names + self._owner.transition_state_names:
            Gs.append(self.E[intermediates_name])
        setattr(self._owner, 'intermediates_Gs', Gs)
        return Gs

    def classified_numerical_jacobian(self, f, x, h=1e-10):
        """
        Calculate the Jacobian matrix of a function at the point x0.
        Modified from numerial_jacobian() in 'functions.py'.

        Not a general-purpose method, just used for given model

        Use differences in opposite directions according to the type
        of G(intermediate or transition state) to avoid stagnated or
        diverging residual.
        """
        x = self._matrix(x)
        x = self._matrix(x).reshape(-1, 1)
        fx = self._matrix(f(x))
        m = len(fx)
        n = len(x)
        J = self._matrix(m, n)
        inter_num = len(self._owner.adsorbate_names)

        for j in xrange(n):
            print j
            xj = x.copy()
            #using delta proportional to xj is more stable
            delta = abs(h*xj[j])
            delta = max(delta, h)

            #differences with different direction
            if j <= inter_num - 1:
                xj[j] += delta
                Jj = (self._matrix(f(xj)) - fx)/(delta)
            else:
                xj[j] -= delta
                Jj = (self._matrix(f(xj)) - fx)/(-delta)

            for i in xrange(m):
                J[i, j] = Jj[i]
        return J

    def get_rate_control(self):
        """
        Expect free energies of intermediates in kinetic model,
        return a matrix of partial derivation wrt intermediates.
        """
        #get Gs
        Gs = self.get_intermediates_Gs()

        kT = self._owner._kB*self._owner.temperature
        epsilon = self._mpf(self.perturbation_size)
        #get dr/dG matrix
        drdG = numerical_jacobian(
            f=self.get_tof, x=Gs,
            num_repr=self.numerical_representation,
            matrix=self._matrix, h=epsilon,
            direction=self.perturbation_direction
        )
        r = self.get_tof(Gs)

        #multiply 1/r to drdG matrix
        diag_matrix = self._linalg.diag([-kT/tof for tof in r])
        DTRC = diag_matrix*drdG
        #covert it to list
        DTRC_list = DTRC.tolist()
        #archive
        self.logger.archive_data('DTRC', DTRC_list)

        return DTRC

    def correct_energies(self):
        "Correct energies of solver"
        #corrections for gas
        if self._owner.gas_thermo_mode == 'shomate_gas':
            correction_dict = self._owner.corrector.shomate_gas()
        for gas_name in correction_dict:
            self.E[gas_name] += correction_dict[gas_name]
        setattr(self, 'energy_correction', True)

        return self.E

    def solve_ode(self):
        """
        Solve the differetial equations, return points of coverages.
        """
        def dtheta_dt(cvgs_tuple, t):
            return self.steady_state_function(cvgs_tuple)

        t = np.arange(0, 30, 0.00001)
        #initial_cvg = (mp.mpf(0.0), mp.mpf(0.0), mp.mpf(0.9), mp.mpf(0.0))
        initial_cvg = self.boltzmann_coverages()
        track = odeint(dtheta_dt, initial_cvg, t)

        return track

    ######################################################
    ######                                          ######
    ###### calculate micro kinetic model with Sympy ######
    ######                                          ######
    ######################################################

    def get_data_symbols(self):
        "Get Sympy Symbol objects tuple for P, G, coverage."
        #get pressure symbols objects
        self.p_sym = tuple([sym.Symbol('p_' + gas_name, real=True)
                            for gas_name in self._owner.gas_names])

        #get coverage symnols objects
        #for adsorbates
        self.ads_theta_sym = tuple(
            [sym.Symbol(r'theta_' + ads_name, real=True, positive=True)
             for ads_name in self._owner.adsorbate_names]
            )
        #for free sites
        fsite_theta_sym = []
        for site_name in self._owner.site_names:
            total = self._owner.species_definitions[site_name]['total']
            #free_site_cvg = sym.Symbol(str(total), is_real=True)
            free_site_cvg = total
            for ads_name in self.classified_adsorbates[site_name]:
                free_site_cvg -= self.extract_symbol(sp_name=ads_name,
                                                     symbol_type='ads_cvg')
            fsite_theta_sym.append(free_site_cvg)
        self.fsite_theta_sym = tuple(fsite_theta_sym)

        #get free energies symbols for each species
        sp_list = self._owner.species_definitions.keys()
        G_sym_list = []
        for idx, sp_name in enumerate(sp_list):
            if sp_name in self._owner.site_names:
                sp_name = '*_' + sp_name
                sp_list[idx] = sp_name
            G_sym_list.append(sym.Symbol('G_' + sp_name, real=True))
        self.G_sym = tuple(G_sym_list)

        #get equilibrium constants(K) symbols for each elementary rxn
        K_sym_list = []
        for i in xrange(len(self.rxns_list)):
            #subscript = i + 1
            K_sym = sym.Symbol('K_' + str(i), real=True)
            K_sym_list.append(K_sym)
        self.K_sym = tuple(K_sym_list)

        self.has_symbols = True
        self.sp_list = sp_list

        return

    def extract_symbol(self, sp_name, symbol_type):
        """
        Expect a species name string,
        symbol_tup must be in
        ['pressure', 'ads_cvg', 'free_site_cvg', 'free_energy'],
        return corresponding symbol from symbol tuple.
        """
        if symbol_type == 'pressure':
            sp_list = self._owner.gas_names
            symbol_tup = self.p_sym
        elif symbol_type == 'ads_cvg':
            sp_list = self._owner.adsorbate_names
            symbol_tup = self.ads_theta_sym
        elif symbol_type == 'free_site_cvg':
            sp_list = self._owner.site_names
            symbol_tup = self.fsite_theta_sym
        elif symbol_type == 'free_energy':
            sp_list = self.sp_list
            symbol_tup = self.G_sym
        else:
            raise ValueError("illegal symbol_type. symbol_type must be in" +
                             "['pressure', 'ads_cvg', 'free_site_cvg', " +
                             "'free_energy']")
        #extract corresponding symbol from symbol tuple
        idx = sp_list.index(sp_name)

        return symbol_tup[idx]

    @staticmethod
    def get_latex_strs(part1, part2, symbols):
        """
        part1 and part2 are parts of left string in equation string,
        symbols is a iterable object e.g. list or tuple.
        """
        latex_strs = []
        for i, symbol in enumerate(symbols):
            left = part1 + str(i+1) + part2
            right = sym.latex(symbol)
            latex_str = left + ' = ' + right + '\n'
            latex_strs.append(latex_str)

        return tuple(latex_strs)

    def get_single_delta_G_symbols(self, elementary_rxn_list):
        """
        Expect a elementary_rxn_list,
        e.g. [['HCOOH_s', '*_s'], ['HCO-OH_s', '*_s'], ['HCO_s', 'OH_s']]
        return sympy expression of delta Gf and Gr.
        e.g. (G_HCO-OH_s - G_HCOOH_s, G_*_s + G_HCO-OH_s - G_HCO_s - G_OH_s)
        """
        if not self.has_symbols:
            raise AttributeError('Solver has no data symbol.')

        #get symbols of state energy
        state_energy_sym_list = []  # list to gather state energy symbols
        for state_list in elementary_rxn_list:
            state_energy_sym = sym.Symbol('0', is_real=True)
            for sp_str in state_list:
                stoichiometry, species_name = self.split_species(sp_str)
                sp_sym = self.extract_symbol(sp_name=species_name,
                                             symbol_type='free_energy')
                if stoichiometry == 1:
                    sp_energy_sym = sp_sym
                else:
                    sp_energy_sym = stoichiometry*sp_sym
                state_energy_sym += sp_energy_sym
            state_energy_sym_list.append(state_energy_sym)

        #get delta G symbols
        IS_energy_sym = state_energy_sym_list[0]
        FS_energy_sym = state_energy_sym_list[-1]

        if len(state_energy_sym_list) == 3:
            TS_energy_sym = state_energy_sym_list[1]
        elif len(state_energy_sym_list) == 2:
            if not hasattr(self._owner, 'state_energy_dict'):
                if not self.has_data:
                    self.get_data_dict()
                self.get_state_energy_dict()

            def get_state_energy(sp_list):
                state_str = ' + '.join(sp_list)
                return self._owner.state_energy_dict[state_str]

            IS_energy = get_state_energy(elementary_rxn_list[0])
            FS_energy = get_state_energy(elementary_rxn_list[-1])
            TS_idx = -1 if IS_energy <= FS_energy else 0
            TS_energy_sym = state_energy_sym_list[TS_idx]

        delta_Gf_sym = TS_energy_sym - IS_energy_sym
        delta_Gr_sym = TS_energy_sym - FS_energy_sym

        return delta_Gf_sym, delta_Gr_sym

    def get_delta_G_symbols(self):
        "Go through elementary_rxns_list to get symbols of delta G."
        delta_Gf_syms, delta_Gr_syms = [], []
        for elementary_rxn_list in self.rxns_list:
            delta_Gf_sym, delta_Gr_sym =\
                self.get_single_delta_G_symbols(elementary_rxn_list)
            delta_Gf_syms.append(delta_Gf_sym)
            delta_Gr_syms.append(delta_Gr_sym)

        self.delta_Gf_syms = delta_Gf_syms
        self.delta_Gr_syms = delta_Gr_syms

        #latex strings
        f_latexs = self.get_latex_strs(part1=r'\Delta G_{', part2=r'+}',
                                       symbols=delta_Gf_syms)
        r_latexs = self.get_latex_strs(part1=r'\Delta G_{', part2=r'-}',
                                       symbols=delta_Gr_syms)
        self.delta_G_latex = (tuple(f_latexs), tuple(r_latexs))

        return delta_Gf_syms, delta_Gr_syms

    def get_K_syms(self):
        "Go through elementary_rxns_list to get symbols of equilibrium constant."
        #get rate constant symbols
        if not hasattr(self, 'kf_syms') or not hasattr(self, 'kr_syms'):
            self.get_rate_constant_syms()
        K_syms = []
        for kf_sym, kr_sym in zip(self.kf_syms, self.kr_syms):
            K_sym = kf_sym/kr_sym
            K_syms.append(K_sym)

        K_syms = tuple(K_syms)
        self.K_expr_syms = K_syms

        return K_syms

    def get_rate_constant_syms(self):
        "Go through elementary_rxns_list to get symbols of rate constants."
        #k_B, h, T = sym.symbols('k_B, h, T', is_real=True)
        k_B, h, T = self.k_B_sym, self.h_sym, self.T_sym
        kf_syms, kr_syms = [], []
        for idx, elementary_rxn_list in\
                enumerate(self.rxns_list):
            if not hasattr(self, 'delta_Gf_syms') or\
                    not hasattr(self, 'delta_Gr_syms'):
                self.get_delta_G_symbols()

            delta_Gf = self.delta_Gf_syms[idx]
            kf_sym = k_B*T/h*sym.E**(-delta_Gf/(k_B*T))
            kf_syms.append(kf_sym)

            delta_Gr = self.delta_Gr_syms[idx]
            kr_sym = k_B*T/h*sym.E**(-delta_Gr/(k_B*T))
            kr_syms.append(kr_sym)

        self.kf_syms, self.kr_syms = kf_syms, kr_syms

        return kf_syms, kr_syms

    def get_single_rate_sym(self, elementary_rxn_list):
        """
        Expect a elementary_rxn_list e.g.
        [['HCOOH_s', '*_s'], ['HCO-OH_s', '*_s'], ['HCO_s', 'OH_s']]

        return corresponding forward rate and reverse rate symbols.
        e.g. [T*k_B*theta_HCOOH_s*(1 - theta_CO_s - theta_H2O_s - theta_HCOOH_s -
              theta_HCO_s - theta_H_s - theta_OH_s)*
              exp((-G_HCO-OH_s + G_HCOOH_s)/(T*k_B))/h,

              T*k_B*theta_HCO_s*theta_OH_s*
              exp((-G_*_s - G_HCO-OH_s + G_HCO_s + G_OH_s)/(T*k_B))/h]
        """
        rxn_idx = self.rxns_list.index(elementary_rxn_list)
        #get rate constant symbols
        if not hasattr(self, 'kf_syms') or not hasattr(self, 'kr_syms'):
            self.get_rate_constant_syms()
        k_syms = self.kf_syms[rxn_idx], self.kr_syms[rxn_idx]  # tuple

        rate_syms = []
        for i in [0, -1]:
            rate_sym = k_syms[i]
            for sp_str in elementary_rxn_list[i]:
                stoichiometry, species_name = self.split_species(sp_str)
                #get species type
                if '*' in species_name:
                    species_name = species_name.split('_')[-1]
                    sp_type = 'site'
                else:
                    sp_type = self._owner.species_definitions[species_name]['type']
                #set symbol_type
                if sp_type == 'gas':
                    symbol_type = 'pressure'
                elif sp_type == 'site':
                    symbol_type = 'free_site_cvg'
                else:
                    symbol_type = 'ads_cvg'

                sp_data_sym = self.extract_symbol(species_name, symbol_type)
                rate_sym *= sp_data_sym**stoichiometry
            rate_syms.append(rate_sym)

        return tuple(rate_syms)

    def get_rate_syms(self):
        rf_syms, rr_syms = [], []
        for elementary_rxn_list in self._owner.elementary_rxns_list:
            rf_sym, rr_sym = self.get_single_rate_sym(elementary_rxn_list)
            rf_syms.append(rf_sym)
            rr_syms.append(rr_sym)

        self.rf_syms = rf_syms
        self.rr_syms = rr_syms

        return rf_syms, rr_syms

    def get_subs_dict(self, **kwargs):
        "get substitution dict(e.g. G, theta, p, constants dicts)."
        #free energy substitution dict
        G_subs_dict = self.get_G_subs_dict()
        #coverage substitution dict
        if 'cvgs_tuple' in kwargs:
            theta_subs_dict = self.get_theta_subs_dict(kwargs['cvgs_tuple'])
        #pressure substitution dict
        p_subs_dict = self.get_p_subs_dict()
        #constants substitution dict
        constants_subs_dict = self.constants_subs_dict
        #get dicts list
        if 'cvgs_tuple' in kwargs:
            dicts_list = [G_subs_dict, theta_subs_dict,
                          constants_subs_dict, p_subs_dict]
        else:
            dicts_list = [G_subs_dict, constants_subs_dict, p_subs_dict]

        #merge dicts
        subs_dict = {}
        for dic in dicts_list:
            subs_dict = dict(subs_dict, **dic)

        return subs_dict

    def get_rate_constants_by_sym(self):
        """
        Calculate rate constants values
        by back substitution to symbol expressions.
        """
        if not hasattr(self, 'kf_syms') or not hasattr(self, 'kr_syms'):
            self.get_rate_constant_syms()
        #get substitution dict(need G_dict and constants dict)
        subs_dict = self.get_subs_dict()

        kfs, krs = [], []
        #calculate kfs
        for kf_sym in self.kf_syms:
            kf = self._mpf(kf_sym.evalf(subs=subs_dict))
            kfs.append(kf)
        #krs
        for kr_sym in self.kr_syms:
            kr = self._mpf(kr_sym.evalf(subs=subs_dict))
            krs.append(kr)

        self.kfs, self.krs = tuple(kfs), tuple(krs)

        return kfs, krs

    def get_rates_by_sym(self, cvgs_tuple):
        """
        Expect a coverages tuple, and then calculate rates values
        by back substitution to symbol expressions,
        return rfs, rrs
        """
        if not hasattr(self, 'rf_syms') or not hasattr(self, 'rr_syms'):
            self.get_rate_syms()
        #get substitution dict(need G, theta, p, constants dicts)
        subs_dict = self.get_subs_dict(cvgs_tuple=cvgs_tuple)
        #calculate rfs
        rfs, rrs = [], []
        for rf_sym in self.rf_syms:
            rf = self._mpf(float(rf_sym.evalf(subs=subs_dict)))
            rfs.append(rf)
        #cal rrs
        for rr_sym in self.rr_syms:
            rr = self._mpf(float(rr_sym.evalf(subs=subs_dict)))
            rrs.append(rr)

        self.rfs, self.rrs = tuple(rfs), tuple(rrs)

        self.logger.archive_data('rates', (self.rfs, self.rrs))

        return tuple(rfs), tuple(rrs)

    def get_G_subs_dict(self):
        "Get values from solver's data dict."
        #get value dict for solver
        if not self.has_data:
            self.get_data_dict()
        #free energy value dict
        G_dict = {}
        for idx, sp_name in enumerate(self.sp_list):
            G_dict.setdefault(self.G_sym[idx], self.E[sp_name])

        return G_dict

    def get_theta_subs_dict(self, cvgs_tuple):
        theta_dict = {}
        for idx, ads_name in enumerate(self._owner.adsorbate_names):
            theta_dict.setdefault(self.ads_theta_sym[idx], cvgs_tuple[idx])

        return theta_dict

    def get_p_subs_dict(self):
        "Get values from solver's data dict."
        p_dict = {}
        for idx, gas_name in enumerate(self._owner.gas_names):
            p_dict.setdefault(self.p_sym[idx], self.p[gas_name])

        return p_dict

    def get_net_rate_syms(self):
        "Go through rfs and rrs, to get net rate symbolic expressions."
        if not hasattr(self, 'rfs_syms') or not hasattr(self, 'rrs_syms'):
            self.get_rate_syms()
        net_rate_syms = []
        for rf_sym, rr_sym in zip(self.rf_syms, self.rr_syms):
            net_rate_sym = rf_sym - rr_sym
            net_rate_syms.append(net_rate_sym)

        self.net_rate_syms = tuple(net_rate_syms)

        return tuple(net_rate_syms)

    def get_net_rates_by_sym(self, cvgs_tuple):
        if not hasattr(self, 'net_rate_syms'):
            self.get_net_rate_syms()
        #get substitution dict
        subs_dict = self.get_subs_dict(cvgs_tuple=cvgs_tuple)
        net_rate_syms_vect = sym.Matrix(self.net_rate_syms)  # col vect
        #back substitution
        net_rates_vect = net_rate_syms_vect.evalf(subs=subs_dict)
        #keep precision
        net_rates_vect = [self._mpf(float(net_rate))
                          for net_rate in net_rates_vect]

        net_rates_tup = tuple(net_rates_vect)
        #archive
        self.logger.archive_data('net_rates', net_rates_tup)

        return net_rates_tup

    def get_tof_syms(self):
        "Return a tuple containing turnover frequencies of gases."
        #get gas coefficients matrix
        if hasattr(self._owner, 'gas_matrix'):
            gas_matrix = self._owner.gas_matrix
        else:
            gas_matrix = \
                self._owner.parser.get_stoichiometry_matrices()[1]
        gas_matrix = -sym.Matrix(gas_matrix)
        #get net rates symbolic expressions vector
        if not hasattr(self, 'net_rate_syms'):
            self.get_net_rate_syms()
        rate_syms_vect = \
            sym.Matrix(self.get_net_rate_syms()).transpose()  # row vector
        #get tof symbolic expression vector(row vector)
        tof_vect = rate_syms_vect*gas_matrix

        tof_tup = tuple(tof_vect)

        return tof_tup

    def get_tof_by_sym(self, cvgs_tuple):
        "Expect a coverage tuple, return a tuple of TOFs."
        tof_syms_vect = sym.Matrix(self.get_tof_syms())
        subs_dict = self.get_subs_dict(cvgs_tuple=cvgs_tuple)
        tof_vect = tof_syms_vect.evalf(subs=subs_dict)
        #keep precision
        tof_vect = [self._mpf(float(tof)) for tof in tof_vect]

        return tuple(tof_vect)

    ##########################################################
    ###### calculate micro kinetic model with Sympy END ######
    ##########################################################


class NewtonRoot(object):  # Hacked from CatMap
    """
    Hacked from MDNewton in mpmath/calculus/optimization.py in order
    to allow for constraints on the solution.
    Find the root of a vector function numerically using Newton's method.

    f is a vector function representing a nonlinear equation system.

    x0 is the starting point close to the root.

    J is a function returning the Jacobian matrix for a point.

    constraint is function to limit x.
    """
    def __init__(self, f, J, x0, constraint, norm,
                 mpfloat, matrix, Axb_solver, **kwargs):
        self.f, self.x0, self.J = f, x0, J
        #below are all function objects
        self._norm = norm
        self._mpf = mpfloat
        self._matrix = matrix
        self._Axb_solver = Axb_solver

#        if 'constraint' in kwargs:
#            self.constraint = kwargs['constraint']
#        else:
#            def constraint(x):
#                return x
#            self.constraint = constraint
        self.real_constraint = constraint

        def quasi_constraint(x):
            return x
        self.quasi_constraint = quasi_constraint

        if 'dtheta_dt_expressions' in kwargs:
            self.dtheta_dt_expressions = kwargs['dtheta_dt_expressions']

    def __iter__(self):

        def vec2tup(col_vector):
            "convert column vector of mpmath or numpy to python tuple."
            if self._mpf == gmpy2.mpfr:  # gmpy
                return tuple(col_vector.reshape(1, -1).tolist()[0])
#            elif self._mpf == mp.mpf:  # mpmath
#                return tuple(col_vector)
#            elif self._mpf == sym.mpmath.mpf:  # sympy
#                return tuple(col_vector)
            else:
                return tuple(col_vector)

        iter_counter = 0
        f = self.f
        J = self.J
        x0 = self.quasi_constraint(self.x0)
        norm = self._norm
        fx = self._matrix(f(x0))
        fxnorm = norm(fx)
        cancel = False
        #x0 = mp.matrix(x0)
        while not cancel:
            iter_counter += 1
            if iter_counter <= 5:
                self.constraint = self.quasi_constraint
            else:
                self.constraint = self.real_constraint
            #get direction of descent
            fx = self._matrix(f(x0))
            fxn = -fx
            Jx = J(self.dtheta_dt_expressions, x0)
            try:
                s = self._Axb_solver(Jx, fxn)  # if use gmpy and numpy,
                #print s                       # lose precision here
            except ZeroDivisionError:
                print 'ZeroDivisionError!'
                cancel = True
                break

            #use golden method to get optimal step size

            def fl(l):
                x1 = self._matrix(x0) + l*s
                fx = self._matrix(f(vec2tup(x1)))
                return norm(fx)
            l = golden(fl)
#            print l
#            l = mp.mpf('1.0')
            x1 = self._matrix(x0) + l*s  # matrix
            x1 = self.constraint(vec2tup(x1))
            if x1 == x0:
                print "Solver: Found stationary point."
                cancel = True
            fx = self._matrix(f(x1))
            x0, fxnorm = x1, norm(fx)

            yield x0, fxnorm, fx
