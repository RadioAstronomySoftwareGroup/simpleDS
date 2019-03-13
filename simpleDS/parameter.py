# -*- mode: python; coding: utf-8 -*
# Copyright (c) 2018 Matthew Kolopanis
# Licensed under the 3-clause BSD License
"""Define Unit Parameter objects: Subclasses of the UVParameter object.

These objects extend the functionality of pyuvdata UVParameter objects to also
include compatibility with Astropy Units and Quantity objects.
"""
from __future__ import print_function, absolute_import, division

import numpy as np
import warnings
from pyuvdata import parameter as uvp, utils as uvutils
import astropy.units as units


class UnitParameter(uvp.UVParameter):
    """SubClass of UVParameters with astropy quantity compatibility.

    Adds checks for Astropy Quantity objects and equality between Quantites.
    """

    def __init__(self, name, required=True, value=None, spoof_val=None,
                 form=(), description='', expected_type=int,
                 acceptable_vals=None, acceptable_range=None,
                 expected_units=None,
                 tols=(1e-05, 1e-08), value_not_quantity=False):
        """Initialize the UVParameter.

        Extra keywords:
            value_not_quantity: (Boolean, default False)
                                Boolean flag used to specify that input value
                                is not an astropy Quantity object, but a
                                UnitParameter is desired over a UVParameter.
        """
        self.value_not_quantity = value_not_quantity
        self.expected_units = expected_units
        if isinstance(value, list) and isinstance(value[0], units.Quantity):
            try:
                value = units.Quantity(value)
            except units.UnitConversionError:
                raise ValueError("Unable to create UnitParameter objects "
                                 "from lists whose elements have "
                                 "non-comaptible units.")
        if isinstance(value, units.Quantity):
            if self.expected_units is None:
                raise ValueError("Input Quantity must also be accompained "
                                 "by the expected unit or equivalent unit. "
                                 "Please set parameter expected_units to "
                                 "an instance of an astropy Units object.")
            if not value.unit.is_equivalent(self.expected_units):
                raise units.UnitConversionError("Input value has units {0} "
                                                "which are not equivalent to "
                                                "expected units of {1}"
                                                .format(value.unit,
                                                        self.expected_units))
            if isinstance(tols, units.Quantity):
                if tols.size > 1:
                    raise ValueError("Tolerance values that are Quantity "
                                     "objects must be a single value to "
                                     "represent the absolute tolerance.")
                else:
                    tols = tuple((0, tols))
            if len(uvutils._get_iterable(tols)) == 1:
                # single value tolerances are assumed to be absolute
                tols = tuple((0, tols))
            if not isinstance(tols[1], units.Quantity):
                print("Given absolute tolerance did not all have units. "
                      "Applying units from parameter value.")
                tols = tuple((tols[0], tols[1] * value.unit))
            if not tols[1].unit.is_equivalent(value.unit):
                raise units.UnitConversionError("Given absolute tolerance "
                                                "did not all have units "
                                                "compatible with given "
                                                "parameter value.")
            tol_unit = tols[1].unit
            tols = tuple((tols[0], tols[1].value))
            super(UnitParameter, self).__init__(name=name, required=required,
                                                value=value,
                                                spoof_val=spoof_val, form=form,
                                                description=description,
                                                expected_type=expected_type,
                                                acceptable_vals=acceptable_vals,
                                                acceptable_range=acceptable_range,
                                                tols=tols)

            self.tols = (tols[0], tols[1] * tol_unit)
        else:
            if value_not_quantity or value is None:
                super(UnitParameter, self).__init__(name=name, required=required,
                                                    value=value,
                                                    spoof_val=spoof_val, form=form,
                                                    description=description,
                                                    expected_type=expected_type,
                                                    acceptable_vals=acceptable_vals,
                                                    acceptable_range=acceptable_range,
                                                    tols=tols)
            else:
                raise ValueError("Input value array is not an astropy Quantity"
                                 " object and the user did not specify "
                                 "value_not_quantity flag.")

    def __eq__(self, other):
        """Equal if classes match and values are identical."""
        if isinstance(other, self.__class__):
            # if both are UnitParameter objects then do new comparison
            if not isinstance(self.value, other.value.__class__):
                print('{name} parameter value classes are different. Left is '
                      '{lclass}, right is {rclass}'.format(name=self.name,
                                                           lclass=self.value.__class__,
                                                           rclass=other.value.__class__))
                return False
            if isinstance(self.value, units.Quantity):
                # check shapes are the same
                if not isinstance(self.tols[1], units.Quantity):
                    self.tols = (self.tols[0], self.tols[1] * self.value.unit)
                if self.value.shape != other.value.shape:
                    print('{name} parameter value is array, shapes are '
                          'different'.format(name=self.name))
                    return False
                elif not self.value.unit.is_equivalent(other.value.unit):
                    print('{name} parameter is Quantity, but have '
                          'non-compatible units '.format(name=self.name))
                    return False
                else:
                    # astropy.units has a units.allclose but only for python 3
                    # already konw the units are compatible so
                    # Convert other to self's units and compare values
                    other.value = other.value.to(self.value.unit)

                    if not np.allclose(self.value.value, other.value.value,
                                       rtol=self.tols[0], atol=self.tols[1].value):
                        print('{name} parameter value is array, values are not '
                              'close'.format(name=self.name))
                        return False
                    else:
                        return True

            else:
                return super(UnitParameter, self).__eq__(other)

        elif issubclass(self.__class__, other.__class__):
            # If trying to compare a UnitParameter to a UVParameter
            # value of the quantity must match the UVParameter
            return self.to_uvp().__eq__(other)
        else:
            print('{name} parameter value classes are different and one '
                  'is not a subclass of the other. Left is '
                  '{lclass}, right is {rclass}'.format(name=self.name,
                                                       lclass=self.__class__,
                                                       rclass=other.__class__))
            return False

    def __ne__(self, other):
        """Not Equal."""
        return not self.__eq__(other)

    def to_uvp(self):
        """Cast self as a UVParameter."""
        if self.value_not_quantity:
            if self.required:
                return uvp.UVParameter(name=self.name, required=self.required,
                                       value=self.value, form=self.form,
                                       description=self.description,
                                       expected_type=self.expected_type,
                                       acceptable_vals=self.acceptable_vals,
                                       acceptable_range=self.acceptable_range,
                                       tols=(self.tols[0], self.tols[1]))
            else:
                return uvp.UVParameter(name=self.name, required=self.required,
                                       value=self.value, spoof_val=self.spoof_val,
                                       form=self.form, description=self.description,
                                       expected_type=self.expected_type,
                                       acceptable_vals=self.acceptable_vals,
                                       acceptable_range=self.acceptable_range,
                                       tols=(self.tols[0], self.tols[1]))
        else:
            # what sould happen here? Warn the user we are comparing a qunatity
            # back to a UVP? might lose units or something. Should it be cast to si?
            # That could mess up things that are intentionally not stored in si.
            warnings.warn('A UnitParameter with quantity value is being cast to '
                          'UVParameter. All quantity information will be lost. '
                          'If this is a comparison that fails, you may need '
                          'to alter the unit of the value to match expected '
                          'UVParameter units.', UserWarning)
            if self.required:
                return uvp.UVParameter(name=self.name, required=self.required,
                                       value=self.value.astype(self.expected_type).value,
                                       form=self.form,
                                       description=self.description,
                                       expected_type=self.expected_type,
                                       acceptable_vals=self.acceptable_vals,
                                       acceptable_range=self.acceptable_range,
                                       tols=(self.tols[0], self.tols[1].value))

            else:
                return uvp.UVParameter(name=self.name, required=self.required,
                                       value=self.value.astype(self.expected_type).value,
                                       spoof_val=self.spoof_val,
                                       form=self.form, description=self.description,
                                       expected_type=self.expected_type,
                                       acceptable_vals=self.acceptable_vals,
                                       acceptable_range=self.acceptable_range,
                                       tols=(self.tols[0], self.tols[1].value))
