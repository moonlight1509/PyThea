from sunpy.coordinates import frames
import astropy.units as u

def load_or_delete_fittings(st):
    selected_row = str(st.session_state.fitting_select)
    dataframe = st.session_state.model_fittings.parameters
    if st.session_state.fit_action == 'Select':
        pass
    elif st.session_state.fit_action == 'Load':
        if st.session_state.coord_system == 'HGS':
            st.session_state.longit = float(dataframe.loc[selected_row,'hgln'])
            st.session_state.latitu = float(dataframe.loc[selected_row,'hglt'])
        elif st.session_state.coord_system == 'HGC':
            st.session_state.longit = float(dataframe.loc[selected_row,'crln'])
            st.session_state.latitu = float(dataframe.loc[selected_row,'crlt'])
        
        if st.session_state.model_fittings.geometrical_model == 'Spheroid':
            keys = ['height', 'kappa', 'epsilon', 'rcenter', 'radaxis', 'orthoaxis1']
        elif st.session_state.model_fittings.geometrical_model == 'GCS':
            keys = ['height', 'alpha', 'kappa', 'tilt']

        for key in keys:
            if key in st.session_state:
                st.session_state[key] = float(dataframe.loc[selected_row,key])
    elif st.session_state.fit_action == 'Delete':
        st.session_state.model_fittings.parameters = dataframe.drop([selected_row])
        del st.session_state.fitting_select
        if len(st.session_state.model_fittings.parameters)<1:
            del st.session_state.model_fittings
        st.experimental_rerun()

    st.session_state.fit_action = 'Select'

def change_long_lat_sliders(st):
    if st.session_state.coord_system == 'HGS':
        center_ = st.session_state.center.transform_to(frames.HeliographicStonyhurst) 
    elif st.session_state.coord_system == 'HGC':
        center_ = st.session_state.center.transform_to(frames.HeliographicCarrington) 
    st.session_state.longit = float(center_.lon.to_value(u.degree))
    st.session_state.latitu = float(center_.lat.to_value(u.degree))
