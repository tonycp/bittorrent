from keys import *
from .bsc_tmp import get_grud_template


CREATE_TEMPLATE = get_grud_template(CREATE_KEY)
UPDATE_TEMPLATE = get_grud_template(UPDATE_KEY)
DELETE_TEMPLATE = get_grud_template(DELETE_KEY)
GET_TEMPLATE = get_grud_template(GET_KEY)
GETALL_TEMPLATE = get_grud_template(GETALL_KEY)
