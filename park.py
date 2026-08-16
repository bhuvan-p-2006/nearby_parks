import streamlit as st
import streamlit.components.v1 as components
import requests
import folium

from streamlit_geolocation import streamlit_geolocation

from math import radians, sin, cos, sqrt, atan2

import time


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Nearby Parks Finder",
    page_icon="🌳",
    layout="wide"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #bbbbbb;
        margin-bottom: 25px;
    }

    .park-card {
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #444444;
        margin-bottom: 10px;
    }

    .distance {
        font-weight: bold;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    '<div class="main-title">🌳 Nearby Parks Finder</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Find parks near your current location using OpenStreetMap.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# HAVERSINE DISTANCE FUNCTION
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):

    """
    Calculate the distance between two GPS coordinates.

    Returns:
        Distance in kilometers
    """

    earth_radius = 6371.0

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2) ** 2
        +
        cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


# ============================================================
# GET COORDINATES FROM OPENSTREETMAP RESULT
# ============================================================

def get_coordinates(element):

    """
    Extract latitude and longitude from an
    OpenStreetMap Overpass element.

    Nodes contain:
        lat
        lon

    Ways/relations contain:
        center.lat
        center.lon
    """

    # Node
    if "lat" in element and "lon" in element:

        return (
            element["lat"],
            element["lon"]
        )

    # Way / Relation
    if "center" in element:

        center = element["center"]

        if (
            "lat" in center
            and
            "lon" in center
        ):

            return (
                center["lat"],
                center["lon"]
            )

    return None, None


# ============================================================
# FIND PARKS USING OVERPASS API
# ============================================================

@st.cache_data(ttl=300)
def find_parks(
    latitude,
    longitude,
    radius_km
):

    """
    Search OpenStreetMap using the Overpass API.
    """

    radius_meters = int(
        radius_km * 1000
    )

    # --------------------------------------------------------
    # OVERPASS QUERY
    # --------------------------------------------------------

    query = f"""
    [out:json][timeout:60];

    (
        nwr["leisure"="park"]
        (around:{radius_meters},{latitude},{longitude});

        nwr["leisure"="garden"]
        (around:{radius_meters},{latitude},{longitude});

        nwr["leisure"="recreation_ground"]
        (around:{radius_meters},{latitude},{longitude});
    );

    out center tags;
    """

    # --------------------------------------------------------
    # OVERPASS SERVERS
    # --------------------------------------------------------

    overpass_servers = [

        "https://overpass-api.de/api/interpreter",

        "https://overpass.kumi.systems/api/interpreter",

        "https://overpass.private.coffee/api/interpreter"

    ]

    # --------------------------------------------------------
    # REQUEST HEADERS
    # --------------------------------------------------------

    headers = {

        "User-Agent":
            "NearbyParksFinder/1.0 "
            "(Streamlit OpenStreetMap application)",

        "Accept":
            "application/json"

    }

    last_error = None

    # --------------------------------------------------------
    # TRY SERVERS
    # --------------------------------------------------------

    for server in overpass_servers:

        try:

            response = requests.post(
                server,
                data=query,
                headers=headers,
                timeout=70
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                data = response.json()

                return data.get(
                    "elements",
                    []
                )

            # ------------------------------------------------
            # SERVER ERROR
            # ------------------------------------------------

            else:

                last_error = (
                    f"Overpass server returned "
                    f"HTTP {response.status_code}"
                )

        except requests.exceptions.Timeout:

            last_error = (
                "The Overpass request timed out."
            )

        except requests.exceptions.ConnectionError:

            last_error = (
                "Could not connect to the Overpass server."
            )

        except requests.exceptions.RequestException as e:

            last_error = str(e)

        except ValueError:

            last_error = (
                "The Overpass server returned invalid JSON."
            )

        # Wait before trying next server
        time.sleep(1)

    # --------------------------------------------------------
    # ALL SERVERS FAILED
    # --------------------------------------------------------

    raise Exception(
        last_error
        or
        "All Overpass servers failed."
    )


# ============================================================
# CREATE FOLIUM MAP
# ============================================================

def create_map(
    latitude,
    longitude,
    parks
):

    """
    Creates the Folium map.

    IMPORTANT:
    This function returns ONLY a Folium Map object.

    We do NOT pass this object to st_folium().
    Instead, we convert it to HTML later.
    """

    # --------------------------------------------------------
    # CREATE MAP
    # --------------------------------------------------------

    park_map = folium.Map(

        location=[
            latitude,
            longitude
        ],

        zoom_start=14,

        control_scale=True

    )

    # --------------------------------------------------------
    # USER LOCATION MARKER
    # --------------------------------------------------------

    folium.Marker(

        location=[
            latitude,
            longitude
        ],

        popup="📍 Your Current Location",

        tooltip="Your Location",

        icon=folium.Icon(
            color="blue",
            icon="home"
        )

    ).add_to(park_map)

    # --------------------------------------------------------
    # USER LOCATION CIRCLE
    # --------------------------------------------------------

    folium.Circle(

        location=[
            latitude,
            longitude
        ],

        radius=100,

        color="blue",

        fill=True,

        fill_opacity=0.15

    ).add_to(park_map)

    # --------------------------------------------------------
    # PARK MARKERS
    # --------------------------------------------------------

    for park in parks:

        park_lat = park.get(
            "latitude"
        )

        park_lon = park.get(
            "longitude"
        )

        # Skip invalid coordinates
        if (
            park_lat is None
            or
            park_lon is None
        ):

            continue

        name = park.get(
            "name",
            "Unnamed Park"
        )

        distance = park.get(
            "distance",
            0
        )

        # ----------------------------------------------------
        # POPUP HTML
        # ----------------------------------------------------

        popup_html = f"""
        <div style="
            width:220px;
            font-family:Arial;
        ">

            <h4>
                🌳 {name}
            </h4>

            <p>
                <b>Distance:</b>
                {distance:.2f} km
            </p>

            <p>
                <b>Latitude:</b>
                {park_lat:.6f}
            </p>

            <p>
                <b>Longitude:</b>
                {park_lon:.6f}
            </p>

        </div>
        """

        # ----------------------------------------------------
        # PARK MARKER
        # ----------------------------------------------------

        folium.Marker(

            location=[
                park_lat,
                park_lon
            ],

            popup=folium.Popup(
                popup_html,
                max_width=300
            ),

            tooltip=name,

            icon=folium.Icon(
                color="green",
                icon="tree"
            )

        ).add_to(park_map)

    # --------------------------------------------------------
    # RETURN MAP
    # --------------------------------------------------------

    return park_map


# ============================================================
# GET USER LOCATION
# ============================================================

st.subheader("📍 Your Location")


location = streamlit_geolocation()


# ============================================================
# CHECK LOCATION OBJECT
# ============================================================

if location is None:

    st.info(
        "Click the location button above and "
        "allow your browser to access your location."
    )

    st.stop()


# ============================================================
# EXTRACT COORDINATES
# ============================================================

latitude = location.get(
    "latitude"
)

longitude = location.get(
    "longitude"
)


# ============================================================
# VALIDATE COORDINATES
# ============================================================

if (
    latitude is None
    or
    longitude is None
):

    st.warning(
        "Your location could not be detected. "
        "Please allow location permission in your browser "
        "and try again."
    )

    st.stop()


# ============================================================
# DISPLAY LOCATION
# ============================================================

st.success(
    f"Your location: "
    f"{latitude:.6f}, "
    f"{longitude:.6f}"
)


# ============================================================
# SEARCH SETTINGS
# ============================================================

st.subheader("🔎 Search Settings")


radius = st.slider(

    "Search radius (km)",

    min_value=1,

    max_value=20,

    value=5,

    step=1

)


# ============================================================
# FIND PARKS BUTTON
# ============================================================

find_button = st.button(

    "🔎 Find Nearby Parks",

    type="primary"

)


# ============================================================
# FIND PARKS
# ============================================================

if find_button:

    with st.spinner(
        f"Searching for parks within "
        f"{radius} km..."
    ):

        try:

            raw_parks = find_parks(

                latitude,

                longitude,

                radius

            )

        except Exception as e:

            st.error(
                "Could not retrieve parks "
                "from OpenStreetMap."
            )

            st.error(
                f"Error details: {e}"
            )

            st.stop()

        # ----------------------------------------------------
        # PROCESS RESULTS
        # ----------------------------------------------------

        parks = []

        for element in raw_parks:

            # -----------------------------------------------
            # GET COORDINATES
            # -----------------------------------------------

            park_lat, park_lon = (
                get_coordinates(element)
            )

            if (
                park_lat is None
                or
                park_lon is None
            ):

                continue

            # -----------------------------------------------
            # GET TAGS
            # -----------------------------------------------

            tags = element.get(
                "tags",
                {}
            )

            # -----------------------------------------------
            # GET NAME
            # -----------------------------------------------

            name = tags.get(
                "name",
                "Unnamed Park"
            )

            # -----------------------------------------------
            # CALCULATE DISTANCE
            # -----------------------------------------------

            distance = haversine_distance(

                latitude,

                longitude,

                park_lat,

                park_lon

            )

            # -----------------------------------------------
            # OSM LINK
            # -----------------------------------------------

            osm_type = element.get(
                "type"
            )

            osm_id = element.get(
                "id"
            )

            osm_link = None

            if (
                osm_type
                and
                osm_id
            ):

                osm_link = (
                    "https://www.openstreetmap.org/"
                    f"{osm_type}/"
                    f"{osm_id}"
                )

            # -----------------------------------------------
            # STORE PARK
            # -----------------------------------------------

            parks.append(

                {

                    "name": name,

                    "latitude": park_lat,

                    "longitude": park_lon,

                    "distance": distance,

                    "osm_link": osm_link

                }

            )

        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        unique_parks = {}

        for park in parks:

            key = (

                round(
                    park["latitude"],
                    6
                ),

                round(
                    park["longitude"],
                    6
                )

            )

            if key not in unique_parks:

                unique_parks[key] = park

        parks = list(
            unique_parks.values()
        )

        # ----------------------------------------------------
        # SORT BY DISTANCE
        # ----------------------------------------------------

        parks.sort(
            key=lambda x:
                x["distance"]
        )

        # ----------------------------------------------------
        # STORE RESULTS
        # ----------------------------------------------------

        st.session_state[
            "parks"
        ] = parks

        st.session_state[
            "search_radius"
        ] = radius


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "parks" in st.session_state:

    parks = st.session_state[
        "parks"
    ]

    # ========================================================
    # NO PARKS
    # ========================================================

    if len(parks) == 0:

        st.warning(

            f"No parks were found "
            f"within {radius} km."

        )

    # ========================================================
    # PARKS FOUND
    # ========================================================

    else:

        st.subheader(

            f"🌳 Found "
            f"{len(parks)} parks"

        )

        # ====================================================
        # CREATE MAP
        # ====================================================

        park_map = create_map(

            latitude,

            longitude,

            parks

        )

        # ====================================================
        # CONVERT FOLIUM MAP TO HTML
        # ====================================================

        map_html = park_map._repr_html_()

        # ====================================================
        # DISPLAY MAP
        # ====================================================
        #
        # IMPORTANT:
        #
        # We are NOT using:
        #
        #     st_folium()
        #
        # This avoids the JSON serialization error.
        #
        # Instead, Folium generates HTML and Streamlit
        # displays that HTML directly.
        #
        # ====================================================

        components.html(

            map_html,

            height=600,

            scrolling=False

        )

        # ====================================================
        # PARK LIST
        # ====================================================

        st.subheader(
            "📋 Nearby Parks"
        )

        for index, park in enumerate(
            parks,
            start=1
        ):

            name = park[
                "name"
            ]

            distance = park[
                "distance"
            ]

            park_lat = park[
                "latitude"
            ]

            park_lon = park[
                "longitude"
            ]

            # ------------------------------------------------
            # PARK CARD
            # ------------------------------------------------

            st.markdown(

                f"""
                <div class="park-card">

                    <h4>
                        {index}. 🌳 {name}
                    </h4>

                    <p>
                        📏 Distance:
                        <span class="distance">
                            {distance:.2f} km
                        </span>
                    </p>

                    <p>
                        📍 Coordinates:
                        {park_lat:.6f},
                        {park_lon:.6f}
                    </p>

                </div>
                """,

                unsafe_allow_html=True

            )

            # ------------------------------------------------
            # OPENSTREETMAP LINK
            # ------------------------------------------------

            if park[
                "osm_link"
            ]:

                st.markdown(

                    "[🗺️ View on OpenStreetMap]"
                    f"({park['osm_link']})"

                )

            st.divider()


# ============================================================
# INFORMATION
# ============================================================

with st.expander(
    "ℹ️ About this application"
):

    st.write(

        """
        This application finds parks near your current
        location using OpenStreetMap.

        Technologies used:

        • Python
        • Streamlit
        • Folium
        • Streamlit Geolocation
        • OpenStreetMap
        • Overpass API

        Your browser provides the GPS location.

        You must allow location access for the application
        to determine your current position.

        The map is generated using Folium and displayed
        directly as HTML inside Streamlit.
        """

    )