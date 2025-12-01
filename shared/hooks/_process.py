from shared.proto import DataSerialize as p


def create_hook(controller, command, func):
    def hook(**kwargs):
        request = p.create_message(controller, command, func, kwargs)
        return request

    return hook
