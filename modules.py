import datetime
import astropy.units as u
from utils import get_hek_flare
from callbacks import (
    load_or_delete_fittings,
    change_long_lat_sliders
)
from config.config_sliders import sliders_dict as sd
from geometrical_models import (
    spheroid,
    gcs
)

def date_and_event_selection(st):
    st.sidebar.markdown('## Date and event selection')
    col1, col2 = st.sidebar.columns(2)
    day = col1.date_input("Select a day to process",
                          datetime.date.today() - datetime.timedelta(days=1))
    initialisation = col2.select_slider("How to initialise?",
                                         options=('Manual','Event','File'), value='Event')
    if initialisation == 'Event':
        selectbox_list, flare_list_ = get_hek_flare(day)
        selectbox_list.insert(0,'Select event')
        event_selected = st.sidebar.selectbox('Solar Events', options=selectbox_list)
        if event_selected!='Select event' and event_selected!='No events returned':
            st.session_state.date_process = flare_list_['event_peaktime'][selectbox_list.index(event_selected)-1]
            st.session_state.date_process = datetime.datetime.strptime(st.session_state.date_process, "%Y-%m-%dT%H:%M:%S")
            st.session_state.event_selected = event_selected
            st.experimental_rerun()
        elif event_selected=='No events returned':
            st.sidebar.warning('Initiate manually')
    elif initialisation == 'Manual':
        with st.sidebar.form("my_form"):
            col1, col2 = st.columns(2)
            ev_id = col1.selectbox('Event ID',
                                   options=['Select','FL', 'CME', 'SHW'])
            time = col2.time_input('Time', datetime.time(12, 0))
            if ev_id!='Select':
                st.session_state.date_process = datetime.datetime.combine(day, time)
                t_ = st.session_state.date_process.strftime("%Y-%m-%dT%H:%M:%S")
                st.session_state.event_selected = f'{ev_id}|{t_}'
                st.experimental_rerun()
            st.form_submit_button()
    elif initialisation == 'File':
        uploaded_files = st.sidebar.file_uploader("Provide a fitting file", accept_multiple_files=False)
        st.sidebar.error('This mode in not availiable yet.')

def fitting_and_slider_options_container(st):
    container = st.sidebar.container()
    with container.expander('Options'):
        col1, col2 = st.columns(2)
        col1.radio('Coordinate system', options=['HGS', 'HGC'], 
                   on_change=change_long_lat_sliders, args=[st], key='coord_system')

        if st.session_state.geometrical_model == 'Spheroid':
            col2.radio('Axes representation', options=['h, e, k', 'r, a, b'], key='sliders_repr_mode')
        elif st.session_state.geometrical_model == 'Ellipsoid':
            col2.radio('Axes representation', options=['h, e, k, a', 'r, a, b, c'], key='sliders_repr_mode')
        elif st.session_state.geometrical_model == 'GCS':
            col2.radio('Axes representation', options=['h, a, k, t'], key='sliders_repr_mode')
        else:
            st.error('Unrecognized geometrical model')

        st.selectbox('Adjustments mode', options=['Standard', '<10Rsun', '>10Rsun', '>30Rsun'],
            key='sliders_adjustment_mode')

        st.select_slider("Plot option for fitting mesh", options=['No plot','Simple','Full'],
            value='Simple', key='plot_mesh_mode')

        fitting_table = st.checkbox("View Fitting Table", value=False, key='fitting_table')

        plt_kinematics = st.checkbox("View Kinematics Plot", value=False, key='plt_kinematics')

def fitting_sliders(st):
    options = {'Spheroid':{'h, e, k': ['height', 'kappa', 'epsilon'],
                           'r, a, b': ['rcenter', 'radaxis', 'orthoaxis1']
                           },
               'GCS':{'h, a, k, t': ['height', 'alpha', 'kappa', 'tilt'],
                      },
               }
    
    adjustments = st.session_state.sliders_adjustment_mode
    
    if st.session_state.geometrical_model=='Spheroid' or \
       st.session_state.geometrical_model=='GCS':
       gmodel = st.session_state.geometrical_model
       rmode = st.session_state.sliders_repr_mode
       sliders = options[gmodel][rmode]
       for slider in sliders:
           st.sidebar.slider(f'{slider} {sd[gmodel][slider]["unit"]}:', # Add units here
                              sd[gmodel][slider][adjustments]['min'],
                              sd[gmodel][slider][adjustments]['max'],
                              sd[gmodel][slider][adjustments]['def'],
                              step=sd[gmodel][slider][adjustments]['step'], key=slider) # * u.R_sun

def final_parameters_gmodel(st):
    if st.session_state.geometrical_model=='Spheroid':
        if st.session_state.sliders_repr_mode=='h, e, k':
            rcenter, radaxis, orthoaxis1 = spheroid.rabc_to_heka(st.session_state.height * u.R_sun,
                                                                 st.session_state.kappa,
                                                                 st.session_state.epsilon)
        elif st.session_state.sliders_repr_mode=='r, a, b':
            rcenter, radaxis, orthoaxis1 = st.session_state.rcenter * u.R_sun, \
                                           st.session_state.radaxis * u.R_sun, \
                                           st.session_state.orthoaxis1 * u.R_sun
        return rcenter, radaxis, orthoaxis1
    elif st.session_state.geometrical_model=='GCS':
        if st.session_state.sliders_repr_mode=='h, a, k, t':
            height = st.session_state.height * u.R_sun
            alpha = st.session_state.alpha * u.degree
            kappa =st.session_state.kappa
            rcenter = gcs.rcenter_(height, alpha, kappa)
        tilt = st.session_state.tilt * u.degree
        return rcenter, height, alpha, kappa, tilt
