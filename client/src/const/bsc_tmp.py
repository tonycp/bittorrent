import copy


BASE_TEMPLATE = {
    "command": "[COMAND]",
    "func": "[Func]",
    "args": {},
    "id": "[ID]",
}


def get_grud_template(command):
    template = copy.deepcopy(BASE_TEMPLATE)
    template["command"] = command
    return template


def set_data_template(template, func, data):
    temp = copy.deepcopy(template)
    temp["func"] = func
    temp["args"] = data
    return temp


def set_id_template(template, id_):
    temp = copy.deepcopy(template)
    temp["id"] = id_
    return temp
