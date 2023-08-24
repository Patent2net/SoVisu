import os

from dateutil import tz

# Define Kibana Parameter
KIBANA_URL = os.getenv('KIBANA_URL', "/kibana")  # default value is "/kibana"

# Define Index Constants
SV_INDEX = os.getenv('SV_INDEX', "sovisu_index")  # default value is "sovisu_index"
SV_LAB_INDEX = os.getenv('SV_LAB_INDEX', "sovisu_index")  # default value is "sovisu_index"

# Define References Constants
SV_HAL_REFERENCES = "domaine_hal_referentiel"
SV_STRUCTURES_REFERENCES = "structures_directory"

# Timezone Configuration
TIMEZONE = tz.gettz('Europe/Paris')
