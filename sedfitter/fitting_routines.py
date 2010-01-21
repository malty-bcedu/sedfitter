import numpy as np

def linear_regression(data, weights, pattern1, pattern2):

    c1 = np.sum(data*pattern1*weights, axis=1)
    c2 = np.sum(data*pattern2*weights, axis=1)
    m11 = np.sum(pattern1*pattern1*weights)
    m12 = np.sum(pattern1*pattern2*weights)
    m22 = np.sum(pattern2*pattern2*weights)

    inv_det = 1./(m11*m22-m12*m12)

    p1 = (m22*c1-m12*c2)*inv_det
    p2 = (m11*c2-m12*c1)*inv_det

    return p1, p2


def optimal_scaling(data, weights, pattern1):
    return np.sum(data*pattern1*weights, axis=2) / np.sum(pattern1*pattern1*weights)

def chi_squared(valid, data, error, weight, model):
    '''
    valid has dimension (n_wav,)
    data has dimension (n_wav, n_models)
    error has dimension(n_wav)
    weight has dimension(n_wav)
    model has dimension (n_wav, n_models)
    '''

    # Calculate the 'default' chi^2 and handle special cases after
    chi2_array = (data - model)**2 * weight

    # Force chi^2 to zero for valid==0
    if chi2_array.ndim == 2:
        chi2_array[:, valid==0] = 0.
    elif chi2_array.ndim == 3:
        chi2_array[:, :, valid==0] = 0.
    else:
        raise Exception("Chi^2 array has unexpected number of dimensions: %i" % chi2_array.ndim)

    # Reset lower limits where model < data
    reset = model < data
    if chi2_array.ndim == 2:
        reset[:, valid<>2] = False
    else:
        reset[:, :, valid<>2] = False
    chi2_array[reset] = -2. * np.log10(1.-error[valid==2])

    # Reset upper limits where model > data
    reset = model > data
    if chi2_array.ndim == 2:
        reset[:, valid<>3] = False
    else:
        reset[:, :, valid<>3] = False
    chi2_array[reset] = -2. * np.log10(1.-error[valid==3])

    # Check that there are no infinities
    chi2_array[np.isinf(chi2_array)] = 1.e30

    return np.sum(chi2_array, axis=chi2_array.ndim - 1)