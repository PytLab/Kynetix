import logging
import os
import unittest

from KMCLib import *

from kynetix.model import KineticModel
from kynetix.functions import *
from kynetix.parsers import *


class KMCParserTest(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_kmc_parser_construction(self):
        " Test kmc parser can be constructed correctly. "
        # Construction.
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()

        # Check the parser class and base class type.
        self.assertTrue(isinstance(parser, KMCParser))
        self.assertEqual(parser.__class__.__base__.__name__, "RelativeEnergyParser")

    def test_get_relative_energies(self):
        " Make sure we can get correct relative energies. "
        # Construction.
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        parser.parse_data(filename="kmc_inputs/rel_energy.py", relative=True)

        ref_e = (0.0, 1.92, -1.92)
        ret_e = parser._KMCParser__get_relative_energies('CO_g + *_t -> CO_t')
        self.assertTupleEqual(ref_e, ret_e)

        ref_e = (0.0, 2.09, -2.09)
        ret_e = parser._KMCParser__get_relative_energies('CO_g + *_b -> CO_b')
        self.assertTupleEqual(ref_e, ret_e)

        ref_e = (0.0, 3.48, -3.48)
        ret_e = parser._KMCParser__get_relative_energies('O2_g + 2*_b -> 2O_b')
        self.assertTupleEqual(ref_e, ret_e)

        ref_e = (0.39, 0.8500000000000001, -0.46)
        ret_e = parser._KMCParser__get_relative_energies('CO_b + O_b <-> CO-O_2b -> CO2_g + 2*_b')
        self.assertTupleEqual(ref_e, ret_e)

    def test_get_rxn_rates(self):
        " Make sure we can get correct forward and reverse rates for a reaction. "
        # Construction.
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        parser.parse_data(filename="kmc_inputs/rel_energy.py", relative=True)

        ref_r = (1575287.974387463, 3.8789566422291146e-14)
        ret_r = parser._KMCParser__get_rxn_rates('CO_b + O_b <-> CO-O_2b -> CO2_g + 2*_b')
        self.assertTupleEqual(ref_r, ret_r)

        ref_r = (215.85343473385328, 4.908397747862737e-34)
        ret_r = parser._KMCParser__get_rxn_rates('O2_g + 2*_b -> 2O_b')
        self.assertTupleEqual(ref_r, ret_r)

        ref_r = (11.535554738754854, 7.067696649263955e-07)
        ret_r = parser._KMCParser__get_rxn_rates('CO_g + *_t -> CO_t')
        self.assertTupleEqual(ref_r, ret_r)

    def test_parse_single_process(self):
        " Make sure we can parse a process dict correctly. "
        # Construction.
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        parser.parse_data(filename="kmc_inputs/rel_energy.py", relative=True)

        process_dict = {"reaction": "CO_b + O_b <-> CO-O_2b -> CO2_g + 2*_b",
                        "description": "CO and O couple and desorption.",
                        "coordinates_group":[[[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
                                             [[0.0, 0.0, 0.0], [0.5, -0.5, 0.0]],
                                             [[0.0, 0.0, 0.0], [-0.5, 0.5, 0.0]],
                                             [[0.0, 0.0, 0.0], [-0.5, -0.5, 0.0]]],
                        "elements_before": ["V", "V"],
                        "elements_after": ["O_s", "O_s"],
                        "basis_sites": [1, 2]}

        processes = parser._KMCParser__parse_single_process(process_dict)

        # Check processes number.
        self.assertEqual(16, len(processes))

        # Check a the first process object.
        p = processes[0]
        self.assertListEqual(p.basisSites(), [1])
        self.assertListEqual(p.elementsBefore(), ["V", "V"])
        self.assertListEqual(p.elementsAfter(), ["O_s", "O_s"])

        # Check coordinates.
        ref_coords = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]
        c = p.localConfigurations()[0]
        ret_coords = c.coordinates().tolist()
        self.assertListEqual(ref_coords, ret_coords)

        # Check a the second process object.
        p = processes[-1]
        self.assertListEqual(p.basisSites(), [2])
        self.assertListEqual(p.elementsBefore(), ["O_s", "O_s"])
        self.assertListEqual(p.elementsAfter(), ["V", "V"])

        # Check coordinates.
        ref_coords = [[0.0, 0.0, 0.0], [-0.5, -0.5, 0.0]]
        c = p.localConfigurations()[0]
        ret_coords = c.coordinates().tolist()
        self.assertListEqual(ref_coords, ret_coords)

    def test_parse_processes(self):
        " Make sure we can parse all processes in kmc_processes.py correctly. "
        # Construction.
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        parser.parse_data(filename="kmc_inputs/rel_energy.py", relative=True)
        p = parser.parse_processes(filename="kmc_inputs/kmc_processes.py")

        self.assertEqual(30, len(p))

    def test_construct_lattice(self):
        " Test we can construct lattice object correctly. "
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        lattice = parser.construct_lattice()

        # Check.
        self.assertTrue(isinstance(lattice, KMCLattice))

        ref_basis = [[0.0, 0.0, 0.0],
                     [0.5, 0.0, 0.0],
                     [0.0, 0.5, 0.0],
                     [0.5, 0.5, 0.0]]
        ret_basis = lattice.basis().tolist()
        self.assertListEqual(ref_basis, ret_basis)

        ref_periodic = (True, True, False)
        ret_periodic = lattice.periodic()
        self.assertTupleEqual(ref_periodic, ret_periodic)

        ref_repetitions = (3, 3, 1)
        ret_repetitions = lattice.repetitions()
        self.assertTupleEqual(ref_repetitions, ret_repetitions)
        ref_sites=[[0.000000, 0.000000, 0.000000],
                   [0.500000, 0.000000, 0.000000],
                   [0.000000, 0.500000, 0.000000],
                   [0.500000, 0.500000, 0.000000],
                   [0.000000, 1.000000, 0.000000],
                   [0.500000, 1.000000, 0.000000],
                   [0.000000, 1.500000, 0.000000],
                   [0.500000, 1.500000, 0.000000],
                   [0.000000, 2.000000, 0.000000],
                   [0.500000, 2.000000, 0.000000],
                   [0.000000, 2.500000, 0.000000],
                   [0.500000, 2.500000, 0.000000],
                   [1.000000, 0.000000, 0.000000],
                   [1.500000, 0.000000, 0.000000],
                   [1.000000, 0.500000, 0.000000],
                   [1.500000, 0.500000, 0.000000],
                   [1.000000, 1.000000, 0.000000],
                   [1.500000, 1.000000, 0.000000],
                   [1.000000, 1.500000, 0.000000],
                   [1.500000, 1.500000, 0.000000],
                   [1.000000, 2.000000, 0.000000],
                   [1.500000, 2.000000, 0.000000],
                   [1.000000, 2.500000, 0.000000],
                   [1.500000, 2.500000, 0.000000],
                   [2.000000, 0.000000, 0.000000],
                   [2.500000, 0.000000, 0.000000],
                   [2.000000, 0.500000, 0.000000],
                   [2.500000, 0.500000, 0.000000],
                   [2.000000, 1.000000, 0.000000],
                   [2.500000, 1.000000, 0.000000],
                   [2.000000, 1.500000, 0.000000],
                   [2.500000, 1.500000, 0.000000],
                   [2.000000, 2.000000, 0.000000],
                   [2.500000, 2.000000, 0.000000],
                   [2.000000, 2.500000, 0.000000],
                   [2.500000, 2.500000, 0.000000]]
        ret_sites = lattice.sites().tolist()
        self.assertListEqual(ref_sites, ret_sites)

        unitcell = lattice.unitCell()
        self.assertTrue(isinstance(unitcell, KMCUnitCell))

    def test_parse_configuration(self):
        " Make sure we can parse the configuration correctly. "
        model = KineticModel(setup_file="kmc_inputs/kmc_parser.mkm",
                             verbosity=logging.WARNING)
        parser = model.parser()
        lattice = parser.construct_lattice()
        config = parser.parse_configuration(lattice, filename="kmc_inputs/kmc_configuration.py")

        # Check types.
        ref_types = ["V"]*36
        ret_types = config.types()
        self.assertListEqual(ref_types, ret_types)

        # Check atom_id_coordinates.
        ref_atom_id_coords=[[0.000000, 0.000000, 0.000000],
                            [0.500000, 0.000000, 0.000000],
                            [0.000000, 0.500000, 0.000000],
                            [0.500000, 0.500000, 0.000000],
                            [0.000000, 1.000000, 0.000000],
                            [0.500000, 1.000000, 0.000000],
                            [0.000000, 1.500000, 0.000000],
                            [0.500000, 1.500000, 0.000000],
                            [0.000000, 2.000000, 0.000000],
                            [0.500000, 2.000000, 0.000000],
                            [0.000000, 2.500000, 0.000000],
                            [0.500000, 2.500000, 0.000000],
                            [1.000000, 0.000000, 0.000000],
                            [1.500000, 0.000000, 0.000000],
                            [1.000000, 0.500000, 0.000000],
                            [1.500000, 0.500000, 0.000000],
                            [1.000000, 1.000000, 0.000000],
                            [1.500000, 1.000000, 0.000000],
                            [1.000000, 1.500000, 0.000000],
                            [1.500000, 1.500000, 0.000000],
                            [1.000000, 2.000000, 0.000000],
                            [1.500000, 2.000000, 0.000000],
                            [1.000000, 2.500000, 0.000000],
                            [1.500000, 2.500000, 0.000000],
                            [2.000000, 0.000000, 0.000000],
                            [2.500000, 0.000000, 0.000000],
                            [2.000000, 0.500000, 0.000000],
                            [2.500000, 0.500000, 0.000000],
                            [2.000000, 1.000000, 0.000000],
                            [2.500000, 1.000000, 0.000000],
                            [2.000000, 1.500000, 0.000000],
                            [2.500000, 1.500000, 0.000000],
                            [2.000000, 2.000000, 0.000000],
                            [2.500000, 2.000000, 0.000000],
                            [2.000000, 2.500000, 0.000000],
                            [2.500000, 2.500000, 0.000000]]
        ret_atom_id_coords = config.atomIDCoordinates().tolist()
        self.assertListEqual(ref_atom_id_coords, ret_atom_id_coords)

        # Check atom_id_types, should be the same as types.
        ref_atom_id_types = tuple(["V"]*36)
        ret_atom_id_types = config.atomIDTypes()
        self.assertTupleEqual(ref_atom_id_types, ret_atom_id_types)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(KMCParserTest)
    unittest.TextTestRunner(verbosity=2).run(suite)

