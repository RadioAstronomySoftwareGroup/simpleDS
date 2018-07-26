"""Calculate Delay Spectrum from pyuvdata object."""
from __future__ import print_function

import os
import sys
import numpy as np
from pyuvdata import UVData
from builtins import range, zip
import astropy.units as units
from astropy.units import Quantity
from astropy import constants as const
from scipy.signal import windows


def jy_to_mk(freqs):
    """Calculate the Jy to mK conversion lambda^2/(2 * K_boltzman)."""
    assert(isinstance(freqs, Quantity))
    jy2t = const.c.to('m/s')**2 / (2 * freqs.to('1/s')**2
                                   * const.k_B)
    return jy2t.to('mK/Jy')


def delay_transform(data_1_array, data_2_array=None,
                    delta_f=1. * units.Hz,
                    window=windows.blackmanharris):
    """Perform the Dealy transform over specified channel rangeself.

    Perform the FFT over frequency using the specified window function
    and cross multiplies all baselines in the data array.

    Arguments:
        data_1_array : (Nbls, Ntimes, Nfreqs) array from utils.get_data_array
                        Can also have shape (Npols, Nbls, Ntimes, Nfreqs)
        data_2_array : same type as data_1_array if take cross-multiplication
                       Defaults to copying data_1_array for auto-correlation
        delta_f: The difference between frequency channels in the data.
                 This is used to properly normalize the Fourier Transform.
                 Must be an astropy Quantity object
        window : Window function used in delay transform.
                 Default is scipy.signal.windows.blackmanharris
    Returns:
        delay_power: (Nbls, Nbls, Ntimes, Nfreqs) array
                     Cross multplies all baselines in data_1_array
                     if pols are present returns
                     (Npols, Nbls, Nbls, Ntimes, Nfreqs)
    """
    if isinstance(data_1_array, Quantity):
        unit = data_1_array.unit
    else:
        unit = 1.

    if not isinstance(delta_f, Quantity):
        raise ValueError('delta_f must be an astropy Quantity object. '
                         'value was : {df}'.format(df=delta_f))

    if data_2_array is None:
        data_2_array = data_1_array.copy()

    if not data_2_array.shape == data_1_array.shape:
        raise ValueError('data_1_array and data_2_array must have same shape, '
                         'but data_1_array has shape {d1_s} and '
                         'data_2_array has shape {d2_s}'
                         .format(d1_s=data_1_array.shape,
                                 d2_s=data_2_array.shape))
    nfreqs = data_1_array.shape[-1]
    win = window(nfreqs).reshape(1, nfreqs)

    # Fourier Transforms should have a delta_f term multiplied
    # This is the proper normalization of the FT but is not
    # accounted for in an fft.
    delay_1_array = np.fft.fft(data_1_array * win, axis=-1)
    delay_1_array = np.fft.fftshift(delay_1_array, axes=-1)
    delay_1_array = delay_1_array * delta_f.to('1/s') * unit

    delay_2_array = np.fft.fft(data_2_array * win, axis=-1)
    delay_2_array = np.fft.fftshift(delay_2_array, axes=-1)
    delay_2_array = delay_2_array * delta_f.to('1/s') * unit

    # Using slicing for cross-multiplication should be quick.
    if len(data_1_array.shape) == 3:
        delay_power = (delay_1_array[None, :, :].conj() *
                       delay_2_array[:, None, :, :])
    else:
        delay_power = (delay_1_array[:, None, :, :].conj() *
                       delay_2_array[:, :, None, :, :])
    return delay_power


def combine_nsamples(nsample_1, nsample_2=None):
    """Combine the nsample arrays for use in cross-multiplication.

    Uses numpy slicing to generate array of all sample cross-multiples.
    Used to find the combine samples for a the delay spectrum.
    The geometric mean is taken between nsamples_1 and nsamples_2 because
    nsmaples array is used to compute thermal variance in the delay spectrum.

    Arguments:
        nsample_1 : (Nbls, Ntimes, Nfreqs) array from utils.get_nsamples_array
                    can also have shape (Npols, Nbls, Ntimes, Nfreqs)
        nsample_2 : same type as nsample_1 if take cross-multiplication
                       Defaults to copying nsample_1 for auto-correlation
    Returns:
        samples_out: (Nbls, Nbls, Nfreqs, Ntimes) array of geometric mean of
                     the input sample arrays.
                     Can also have shape (Npols, Nbls, Nbls, Ntimes, Nfreqs)
    """
    if nsample_2 is None:
        nsample_2 = nsample_1.copy()

    if not nsample_1.shape == nsample_2.shape:
        raise ValueError('nsample_1 and nsample_2 must have same shape, '
                         'but nsample_1 has shape {d1_s} and '
                         'nsample_2 has shape {d2_s}'
                         .format(d1_s=nsample_1.shape,
                                 d2_s=nsample_2.shape))

    # The nsamples array is used to construct the thermal variance
    # Cross-correlation takes the geometric mean of thermal variance.
    if len(nsample_1.shape) == 3:
        samples_out = np.sqrt(nsample_1[None, :, :] *
                              nsample_2[:, None, :, :])
    else:
        samples_out = np.sqrt(nsample_1[:, None, :, :] *
                              nsample_2[:, :, None, :, :])
    return samples_out


def remove_auto_correlations(data_array):
    """Remove the auto-corrlation term from input array.

    Argument:
        data_array : (Nbls, Nbls, Ntimes, Nfreqs)
                     Removes same baseline diagonal along the first 2 diemsions
    Returns:
        data_out : (Nbls * (Nbls-1), Ntimes, Nfreqs) array.
                   if input has pols: (Npols, Nbls * (Nbls -1), Ntimes, Nfreqs)
    """
    if len(data_array.shape) == 4:
        Nbls = data_array.shape[0]
    elif len(data_array.shape) == 5:
        Nbls = data_array.shape[1]
    else:
        raise ValueError('Input data_array must be of type '
                         '(Npols, Nbls, Nbls, Ntimes, Nfreqs) or '
                         '(Nbls, Nbls, Ntimes, Nfreqs) but data_array'
                         'has shape {0}'.format(data_array.shape))
    # make a boolean index array with True off the diagonal and
    # False on the diagonal.
    indices = np.logical_not(np.diag(np.ones(Nbls, dtype=bool)))
    if len(data_array.shape) == 4:
        data_out = data_array[indices]
    else:
        data_out = data_array[:, indices]

    return data_out


def calculate_noise_power(nsamples, freqs, inttime, trcvr):
    """Generate power as given by the radiometry equation.

    noise_power = Tsys/sqrt(delta_frequency * inttime )

    Computes the system temperature using the equation:
        T_sys = 180K * (nu/180MHz)^(-2.55) + T_receiver
    Arguments:
        nsamples: The nsamples array from which to compute thermal variance
        freqs: The observed frequncies
        trcvr: The receiver temperature of the instrument in K
    Returns:
        noise_power: White noise with the same shape as nsamples input.
    """
    if not isinstance(inttime, Quantity):
        raise ValueError('inttime must be an astropy Quantity object. '
                         'value was: {t}'.format(t=inttime))
    if not isinstance(freqs, Quantity):
        raise ValueError('freqs must be an astropy Quantity object. '
                         'value was: {fq}'.format(fq=freqs))
    if not isinstance(trcvr, Quantity):
        raise ValueError('trcvr must be an astropy Quantity object. '
                         ' value was: {temp}'.format(temp=trcvr))

    Tsys = 180. * units.K * np.power(freqs.to('GHz')/(.18 * units.GHz), -2.55)
    Tsys += trcvr.to('K')
    delta_f = np.diff(freqs)[0]
    noise_power = (Tsys.to('K')
                   / np.sqrt(delta_f.to('1/s') * inttime.to('s') * nsamples))
    return noise_power


def generate_noise(noise_power):
    """Generate noise given an input array of noise power.

    Argument:
        noise_power: N-dimensional array of noise power to generate white
                     noise.
    Returns:
        noise: Complex white noise drawn from a Gaussian distribution with
               width given by the value of the input noise_power array.
    """
    # divide by sqrt(2) to conserve total noise amplitude over real and imag
    noise = noise_power * (1 * np.random.normal(size=noise_power.shape)
                           + 1j * np.random.normal(size=noise_power.shape))
    noise /= np.sqrt(2)
    return noise
