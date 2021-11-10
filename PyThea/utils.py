"""
    PyThea: A software package to reconstruct the 3D structure of CMEs and
    shock waves using multi-viewpoint remote-sensing observations.
    Copyright (C) 2021  Athanasios Kouloumvakos

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import datetime
import io
import json
from copy import copy
from operator import attrgetter

import astropy.units as u
import matplotlib.colors as colors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import sunpy.map
from config.selected_bodies import bodies_dict
from config.selected_imagers import imager_dict
from scipy.interpolate import UnivariateSpline
from sunpy.coordinates import get_horizons_coord
from sunpy.map.maputils import contains_coordinate
from sunpy.net import Fido
from sunpy.net import attrs as a
from sunpy_dev.map.maputils import (prepare_maps, filter_maps,
                                    difference_maps, normalize_exposure,
                                    maps_sequence_processing)


def get_hek_flare(day):
    flare_list = Fido.search(a.Time(day, day + datetime.timedelta(days=1)),
                            a.hek.EventType("FL"),
                            a.hek.FL.GOESCls > "B1.0",
                            a.hek.OBS.Observatory == "GOES")
    if len(flare_list["hek"]) == 0:
        selectbox_list = ['No events returned',]
        flare_list_ = []
    else:
        flare_list_ = flare_list["hek"]["event_starttime", "event_peaktime",
                                        "event_endtime", "fl_goescls",
                                        "fl_peakflux","hgs_x","hgs_y","ar_noaanum"]
        selectbox_list = []
        for flares in flare_list_:
            selectbox_list.append((f'FL{flares["fl_goescls"]}|{flares["event_peaktime"]}'))

    return selectbox_list, flare_list_

def make_figure(map, image_mode, clim=[-20,20], clip_model=True):
    fig = plt.figure()
    axis = plt.subplot(projection=map)
    #TODO: For plain images or when EUVIA-B are used, this does not work very well.
    if image_mode=='Plain':
        map.plot()
    else:
        map.plot(cmap='Greys_r',
                 norm=colors.Normalize(vmin=clim[0], vmax=clim[1]))
    map.draw_limb()
    #map.draw_grid(linewidth=2, color='red') # TODO: This takes too much computation time. Maybe for AIA or EUVI?
    yax = axis.coords[1]
    yax.set_ticklabel(rotation=90)
    if clip_model:
        axis.set_xlim([0, map.data.shape[0]])
        axis.set_ylim([0, map.data.shape[1]])

    return fig, axis

def plot_bodies(axis, bodies_list, smap):
    for body in bodies_list:
        body_coo = get_horizons_coord(bodies_dict[body][0], smap.date)
        if contains_coordinate(smap, body_coo):
            axis.plot_coord(body_coo, 'o', color=bodies_dict[body][1],
                fillstyle='none', markersize=6, label=body)

def download_fits(date_process, imager, time_range=[-1,1]):
    timerange = a.Time(date_process + datetime.timedelta(hours=time_range[0]),
                       date_process + datetime.timedelta(hours=time_range[1]))

    map_ = {}
    args = imager_dict[imager][0]
    result = Fido.search(timerange, *args)
    print(result)
    if len(result['vso'])!=0:
        downloaded_files = Fido.fetch(result)
        map_ = sunpy.map.Map(downloaded_files)
    else:
        map_ = []

    return map_

def maps_process(session_state, imagers_list, image_mode):
    session_state.map = {}
    session_state.imagers_list_ = []
    for imager in imagers_list:
        extra = imager_dict[imager][1]
        if imager not in session_state.map_ or session_state.map_[imager]==[]:
            pass
        else:
            session_state.map[imager] = filter_maps(session_state.map_[imager], extra)
            session_state.map[imager] = prepare_maps(session_state.map[imager], extra)
            session_state.map[imager] = maps_sequence_processing(session_state.map[imager],
                                                                 seq_type=image_mode)
            session_state.imagers_list_.append(imager)

    return session_state

def maps_clims(session_state, imagers_list):
    session_state.map_clim = {}
    for imager in imagers_list:
        if imager not in session_state.map or session_state.map[imager]==[]:
            pass
        else:
            map_ = session_state.map[imager][0]
            session_state.map_clim[imager] = [np.nanquantile(map_.data, 0.20), np.nanquantile(map_.data, 0.80)]

    return session_state

# TODO: Implement units here
class model_fittings:
    def __init__(self, event_selected, date_process, geometrical_model, model_parameters):
        self.event_selected = event_selected
        self.date_process = date_process
        self.geometrical_model = geometrical_model
        self.parameters = model_parameters

    def model_id(self):
        str_id = self.event_selected.replace('-','').replace(':','').replace('|','D').replace('.','p') + 'M' + self.geometrical_model
        return str_id

    def to_jsonbuffer(self):
        parameters = copy(self.parameters)
        parameters['time'] = parameters.index.strftime("%Y-%m-%dT%H:%M:%S.%f")
        parameters = parameters.to_dict(orient='list')
        fitting_full_file = {'event_selected': self.event_selected,
                             'date_process': self.date_process,
                             'geometrical_model': {'type':self.geometrical_model,
                                                   'parameters': parameters},
                             }
        json_buffer = io.BytesIO()
        json_buffer.write(json.dumps(fitting_full_file,indent=' ').encode())

        return json_buffer

def plot_fitting_model(model, fit_args, plt_type='HeightT'):
    palete = sns.color_palette("deep")
    parameters = {'Spheroid':
                             {'height': ['+', '', palete[3], 'h-apex'],
                              'orthoaxis1': ['x', '', palete[0], 'r-axis1'],
                              },
                  'Ellipsoid': {'height': ['+', '', palete[3], 'r-apex'],
                                'orthoaxis1': ['x', '', palete[0], 'r-axis1'],
                                'orthoaxis2': ['x', '', palete[2], 'r-axis2'],
                                },
                  'GCS': {'height': ['+', '', palete[3], 'h-apex'],
                          'rappex': ['x', '', palete[0], 'r-apex'],
                                },
                      }
    parameters = parameters[model.geometrical_model]
    # Height vs time
    fig = plt.figure(figsize=(5.5,5.5), tight_layout=True)
    axis = plt.subplot()
    for p in parameters.keys():
        if plt_type == 'HeightT':
            plt.plot(model.parameters.index,
                     model.parameters[p],
                     marker=parameters[p][0],
                     linestyle=parameters[p][1],
                     color=parameters[p][2],
                     label=parameters[p][3]) # label='fit: a=%5.3f, b=%5.3f, c=%5.3f' % tuple(popt)
            if len(model.parameters[p])-1 > fit_args['order']:
                # How to get confidence intervals from curve_fit?
                fit = parameter_fit(model.parameters.index, model.parameters[p], fit_args)
                plt.plot(fit['best_fit_x'], fit['best_fit_y'], '-', color=parameters[p][2])
                plt.fill_between(fit['best_fit_x'], fit['sigma_bounds']['up'], fit['sigma_bounds']['low'],
                                 color = parameters[p][2], alpha = 0.20)
                if fit_args['type'] == 'spline':
                    plt.fill_between(fit['best_fit_x'], fit['sigv_bounds']['up'], fit['sigv_bounds']['low'],
                                     color = parameters[p][2], alpha = 0.05)
            else:
                plt.plot(model.parameters.index, model.parameters[p], '--', color=parameters[p][2])
            ylabel = 'Height [Rsun]'
        elif plt_type == 'SpeedT':
            if len(model.parameters[p])-1 > fit_args['order']:
                # How to get confidence intervals from curve_fit?
                fit = parameter_fit(model.parameters.index, model.parameters[p], fit_args)
                Rs2km = (1 * u.R_sun).to_value(u.km)
                sec = 24*60*60
                speed_best_fit = (Rs2km/sec) * np.gradient(fit['best_fit_y'], fit['best_fit_x_num'])
                speed_bound_upper = (Rs2km/sec) * np.gradient(fit['sigma_bounds']['up'], fit['best_fit_x_num'])
                speed_bound_lower = (Rs2km/sec) * np.gradient(fit['sigma_bounds']['low'], fit['best_fit_x_num'])
                plt.plot(fit['best_fit_x'], speed_best_fit, '-', color=parameters[p][2], label=parameters[p][3])
                plt.fill_between(fit['best_fit_x'], speed_bound_lower, speed_bound_upper,
                                 color = parameters[p][2], alpha = 0.20)
                if fit_args['type'] == 'spline':
                    plt.fill_between(fit['best_fit_x'], (Rs2km/sec) * fit['sigv_bounds']['dlow'], (Rs2km/sec) * fit['sigv_bounds']['dup'],
                                     color = parameters[p][2], alpha = 0.05)
            else:
                pass
            ylabel = 'Speed [km/s]'
    plt.xlabel('Time [UT]')
    plt.ylabel(ylabel)
    plt.title('Event: '+model.event_selected+' | ' + fit_args['type'] + str(fit_args['order']))
    plt.gca().set_ylim(bottom=0)
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y\n%b-%d\n%H:%M"))
    fig.autofmt_xdate(bottom=0, rotation=0, ha='center')
    plt.legend(loc='lower right')

    return fig

def parameter_fit(x, y, fit_args):
    def fit_func(x, a, b, c):
        return a * x**2 + b * x + c

    xx = (mdates.date2num(x) - mdates.date2num(x[0]))
    xxx = np.linspace(xx.min(), xx.max(), 120)
    dd = mdates.num2date(xxx + mdates.date2num(x[0]))

    if fit_args['type'] == 'poly':
        ## scipy.optimize.curve_fit and numpy.polyfit
        popt, pcov = np.polyfit(xx, y, fit_args['order'], full=False, cov=True) #curve_fit(fit_func, xx, y)
        sigma = np.sqrt(np.diagonal(pcov)) # calculate sigma from covariance matrix
        best_fit = np.polyval(popt, xxx) #fit_func(xxx, *popt)
        sigma_bound_up = np.polyval((popt + sigma), xxx) #fit_func(xxx, *(popt + sigma))
        sigma_bound_low = np.polyval((popt - sigma), xxx) #fit_func(xxx, *(popt - sigma))
        fitting = {'popt': popt,
                   'pcov': pcov,
                   'sigma': sigma,
                   'best_fit_x_num': xxx,
                   'best_fit_x': dd,
                   'best_fit_y': best_fit,
                   'sigma_bounds': {'up':sigma_bound_up,
                                    'low':sigma_bound_low},
                   }
    elif fit_args['type'] == 'spline':
        spl = UnivariateSpline(xx, y, s=fit_args['smooth'], k=fit_args['order'])
        resid = y - spl(xx) # true - prediction
        sigma = np.nanstd(resid, axis=0) # sigma = std(res)
        best_fit = spl(xxx)
        sigma_bound_up = best_fit + sigma
        sigma_bound_low = best_fit - sigma

        sv_bound_up, sv_bound_low, sv_bound_dup, sv_bound_dlow = best_fit, best_fit, np.gradient(best_fit, xxx), np.gradient(best_fit, xxx)
        for i in range(0,100):
            spl = UnivariateSpline(xx, y, s=i/100, k=fit_args['order']);
            sv_bound_up = np.maximum(sv_bound_up, spl(xxx))
            sv_bound_low = np.minimum(sv_bound_low, spl(xxx))
            sv_bound_dup = np.maximum(sv_bound_dup, np.gradient(spl(xxx), xxx))
            sv_bound_dlow = np.minimum(sv_bound_dlow, np.gradient(spl(xxx), xxx))

        fitting = {'spl': spl,
                   'sigma': sigma,
                   'best_fit_x_num': xxx,
                   'best_fit_x': dd,
                   'best_fit_y': best_fit,
                   'sigma_bounds': {'up':sigma_bound_up,
                                    'low':sigma_bound_low},
                   'sigv_bounds': {'up':sv_bound_up,
                                   'low':sv_bound_low,
                                   'dup':sv_bound_dup,
                                   'dlow':sv_bound_dlow},
                   }
    return fitting
