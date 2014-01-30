from __future__ import print_function, division

import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
from copy import deepcopy

from astropy.table import Table
from astropy.convolution import Tophat2DKernel

import numpy as np
from scipy.ndimage import convolve

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from .fit_info import FitInfo
from .extinction import Extinction
from .models import load_parameter_table
from .utils import io
from .utils.formatter import LogFormatterMathtextAuto

KERNEL = Tophat2DKernel(5.5,x_size=11,y_size=11,mode='oversample').array
KERNEL /= KERNEL.max()  # normalize so maximum is 1

plt.rc('text', usetex=False)
plt.rc('axes', titlesize='small')
plt.rc('axes', labelsize='small')
plt.rc('xtick', labelsize='x-small')
plt.rc('ytick', labelsize='x-small')
plt.rc('font', family='serif')
plt.rc('axes', linewidth=0.5)
plt.rc('patch', linewidth=0.5)

fp = FontProperties(size='small')


def get_axes(fig, label=None):
    vxmin, vxmax = 1.5, 4.5
    vymin, vymax = 1.0, 4.0
    width, height = fig.get_figwidth(), fig.get_figheight()
    rect = [vxmin / width, vymin / width, (vxmax - vxmin) / width, (vymax - vymin) / height]
    return fig.add_axes(rect, label=label)


def plot_params_2d(input_file, parameter_x, parameter_y, output_dir=None,
                   select_format=("N", 1), log_x=False, log_y=True,
                   label_x=None, label_y=None, additional={}, plot_name=True,
                   format='eps'):
    """
    Make histogram plots of parameters

    Parameters
    ----------
    input_file : str
        File containing the fit information
    parameter_x : str
        The parameter to plot on the x-axis
    parameter_y : str
        The parameter to plot on the y-axis
    output_dir : str, optional
        If specified, plots are written to that directory
    select_format : tuple, optional
        Tuple specifying which fits should be plotted. See the documentation
        for a description of the tuple syntax.
    log_x : bool, optional
        Whether to plot the x-axis values in log space
    log_y : bool, optional
        Whether to plot the y-axis values in log space
    label_x : str, optional
        The x-axis label (if not specified, the parameter name is used)
    label_y : str, optional
        The y-axis label (if not specified, the parameter name is used)
    additional : dict, optional
        A dictionary specifying additional parameters not listed in the
        parameter list for the models. Each item of the dictionary should
        itself be a dictionary giving the values for each model (where the key
        is the model name).
    plot_name: bool, optional
        Whether to show the source name on the plot(s).
    format: str, optional
        The file format to use for the plot, if output_dir is specified.

    """

    npix = 1024

    if output_dir is None:
        raise ValueError("No output directory has been specified")

    # Create output directory
    io.create_dir(output_dir)

    # Open output file
    fin = open(input_file, 'rb')

    # Read in header of output file
    model_dir = pickle.load(fin)
    filters = pickle.load(fin)
    extinction = pickle.load(fin)

    # Read in table of parameters for model grid
    t = load_parameter_table(model_dir)

    # Sort alphabetically
    t['MODEL_NAME'] = np.char.strip(t['MODEL_NAME'])
    t.sort('MODEL_NAME')
    tpos = deepcopy(t)
    if log_x:
        tpos = tpos[tpos[parameter_x] > 0.]
    if log_y:
        tpos = tpos[tpos[parameter_y] > 0.]

    # Initialize figure
    fig = plt.figure()
    ax = get_axes(fig, label='main')

    # Find range of values
    xmin, xmax = tpos[parameter_x].min(), tpos[parameter_x].max()
    ymin, ymax = tpos[parameter_y].min(), tpos[parameter_y].max()

    # Compute histogram
    if log_x and log_y:
        gray_all, ex, ey = np.histogram2d(np.log10(tpos[parameter_x]),
                                          np.log10(tpos[parameter_y]), bins=npix,
                                          range=[[np.log10(xmin), np.log10(xmax)],
                                                 [np.log10(ymin), np.log10(ymax)]])
    elif log_x:
        gray_all, ex, ey = np.histogram2d(np.log10(tpos[parameter_x]),
                                          tpos[parameter_y], bins=npix,
                                          range=[[np.log10(xmin), np.log10(xmax)],
                                                 [ymin, ymax]])
    elif log_y:
        gray_all, ex, ey = np.histogram2d(tpos[parameter_x],
                                          np.log10(tpos[parameter_y]), bins=npix,
                                          range=[[xmin, xmax],
                                                 [np.log10(ymin), np.log10(ymax)]])
    else:
        gray_all, ex, ey = np.histogram2d(tpos[parameter_x],
                                          tpos[parameter_y], bins=npix,
                                          range=[[xmin, xmax],
                                                [ymin, ymax]])

    gray_all = convolve(gray_all, KERNEL)
    gray_all = np.clip(gray_all, 0., 13.)

    # Grayscale showing all models. Since pcolormesh is very slow for PDF, we
    # create a 'ghost' axis which is already in log space.
    ax_log = get_axes(fig, label='log')
    ax_log.axis('off')
    ax_log.imshow(gray_all.transpose(), cmap='binary', vmin=0, vmax=40., extent=[ex[0], ex[-1], ey[0], ey[-1]], aspect='auto')

    ax.set_xlabel(parameter_x if label_x is None else label_x)
    ax.set_ylabel(parameter_y if label_y is None else label_y)

    if log_x:
        ax.set_xscale('log')
        ax.xaxis.set_major_formatter(LogFormatterMathtextAuto())
    if log_y:
        ax.set_yscale('log')
        ax.yaxis.set_major_formatter(LogFormatterMathtextAuto())

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    if log_x:
        ax_log.set_xlim(np.log10(xmin), np.log10(xmax))
    else:
        ax_log.set_xlim(xmin, xmax)

    if log_y:
        ax_log.set_ylim(np.log10(ymin), np.log10(ymax))
    else:
        ax_log.set_ylim(ymin, ymax)

    ax.set_autoscale_on(False)
    ax_log.set_autoscale_on(False)

    pfits = None
    source_label = None

    while True:  # Loop over the fits

        # Read in next fit
        try:
            info = pickle.load(fin)
        except EOFError:
            break

        # Remove previous histogram
        if pfits is not None:
            pfits.remove()
        if source_label is not None:
            source_label.remove()

        # Filter fits
        info.keep(select_format[0], select_format[1])

        # Get filtered and sorted table of parameters
        tsorted = info.filter_table(t, additional=additional)

        pfits = ax.scatter(tsorted[parameter_x], tsorted[parameter_y], c='black', s=10)

        if plot_name:
            source_label = ax.text(0.5, 0.95, info.source.name,
                                   horizontalalignment='center',
                                   verticalalignment='center',
                                   transform=ax.transAxes,
                                   fontproperties=fp, zorder=200)
        # Save to file
        filename = "%s/%s.%s" % (output_dir, info.source.name, format)
        fig.savefig(filename, bbox_inches='tight', facecolor='none', dpi=300)

    # Close input and output files
    fin.close()

    plt.close(fig)
